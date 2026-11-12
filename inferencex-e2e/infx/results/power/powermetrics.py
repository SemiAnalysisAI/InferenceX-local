"""Validate a Mac's powermetrics samples against one AgentX window and patch its aggregate.

The samples come from ``infx.bench.powermetrics``. The power metrics are the GPU's alone, as their
names and schema say; the CPU's power and the whole chip's are published as the CPU-side metrics.
As in ``multinode``, invalid telemetry records ``power_valid=0`` and a validation sidecar, and only
``REQUIRE_POWER`` lets that fail the point.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
from collections.abc import Mapping
from pathlib import Path

from . import POWER_METRIC_SCHEMA_VERSION, WHOLE_METRIC_KEYS, with_power_metrics
from .audit import audit_summary
from .common import (
    MAX_SAMPLE_GAP_SECONDS,
    BenchmarkData,
    _bracketing_sequence,
    _integrate_device,
    _load_benchmark_data,
    _percentile_total_power,
    _write_json_atomic,
    audit_metrics,
    benchmark_window_payload,
)

GPU = "gpu"
CPU = "cpu"
CHIP = "chip"
# The sampler's column for each rail. The chip is the CPU, GPU and ANE together.
COLUMNS = {GPU: "gpu_w", CPU: "cpu_w", CHIP: "combined_w"}

Samples = list[tuple[float, float]]


def _read_samples(path: Path) -> tuple[dict[str, Samples], list[str]]:
    """Each rail's ``(time, watts)`` rows of ``path`` and any reason they cannot be used."""
    try:
        with path.open(newline="") as stream:
            rows = [
                (float(row["timestamp_unix"]), *(float(row[column]) for column in COLUMNS.values()))
                for row in csv.DictReader(stream)
            ]
    except FileNotFoundError:
        return {}, ["samples_csv_missing"]
    except (OSError, KeyError, TypeError, ValueError):
        return {}, ["samples_csv_malformed"]
    finite = all(math.isfinite(value) for row in rows for value in row)
    increasing = all(earlier[0] < later[0] for earlier, later in itertools.pairwise(rows))
    if not (finite and increasing):
        return {}, ["samples_csv_malformed"]
    return {rail: [(row[0], row[i]) for row in rows] for i, rail in enumerate(COLUMNS, 1)}, []


def _cpu_metrics(samples: Mapping[str, Samples], benchmark: BenchmarkData) -> dict[str, float]:
    """The CPU's power and the whole chip's over ``benchmark``'s window.

    The chip is published as the module rail. Like a superchip module it holds the GPU too, so it
    is not to be added to the CPU or GPU metrics.
    """
    start, end = benchmark.start_unix, benchmark.end_unix
    cpu = _integrate_device(samples[CPU], start_unix=start, end_unix=end)
    chip = _integrate_device(samples[CHIP], start_unix=start, end_unix=end)
    return {
        "avg_cpu_socket_power_w": cpu / (end - start),
        "avg_total_cpu_power_w": cpu / (end - start),
        "total_cpu_energy_j": cpu,
        "avg_total_module_power_w": chip / (end - start),
        "total_module_energy_j": chip,
    }


def _metrics(samples: Samples, benchmark: BenchmarkData) -> dict[str, float]:
    """The whole-deployment power metrics of the one GPU over ``benchmark``'s window."""
    start, end = benchmark.start_unix, benchmark.end_unix
    energy = _integrate_device(samples, start_unix=start, end_unix=end)
    p75 = _percentile_total_power([samples], start_unix=start, end_unix=end, quantile=0.75)
    p90 = _percentile_total_power([samples], start_unix=start, end_unix=end, quantile=0.9)
    total_tokens = benchmark.total_input_tokens + benchmark.total_output_tokens
    return {
        "avg_power_w": energy / (end - start),
        "p75_power_w": p75,
        "p75_total_gpu_power_w": p75,
        "p90_power_w": p90,
        "p90_total_gpu_power_w": p90,
        "avg_total_gpu_power_w": energy / (end - start),
        "total_gpu_energy_j": energy,
        "joules_per_successful_query": energy / benchmark.completed,
        "joules_per_input_token": energy / benchmark.total_input_tokens,
        "joules_per_output_token": energy / benchmark.total_output_tokens,
        "joules_per_total_token": energy / total_tokens,
    }


def validate(
    *,
    samples_path: Path,
    bench_result: Path,
    agg_result: Path,
    validation_result: Path,
    audit_source: str,
) -> bool:
    """Write the sidecar, patch ``agg_result``, and return whether the power is valid.

    Raises ``OSError`` or ``ValueError`` when the aggregate cannot be read or written.
    """
    benchmark, reasons = _load_benchmark_data(bench_result)
    samples, sample_reasons = _read_samples(samples_path)
    gpu = samples.get(GPU, [])
    reasons += sample_reasons
    sequence = None
    if benchmark is not None and not sample_reasons:
        times = tuple(timestamp for timestamp, _ in gpu)
        sequence = _bracketing_sequence(times, benchmark.start_unix, benchmark.end_unix)
        if sequence is None:
            reasons.append("measurement_window_not_bracketed")
    largest_gap = max(
        (later - earlier for earlier, later in itertools.pairwise(sequence or ())), default=0.0
    )
    if largest_gap > MAX_SAMPLE_GAP_SECONDS:
        reasons.append("sample_gap_exceeded")
    metrics: dict[str, float] = {}
    cpu_metrics: dict[str, float] = {}
    if not reasons and benchmark is not None:
        metrics, cpu_metrics = _metrics(gpu, benchmark), _cpu_metrics(samples, benchmark)
    validation = {
        "schema_version": 1,
        "power_valid": not reasons,
        "reasons": reasons,
        "telemetry_source": str(samples_path),
        "power_scope": GPU,
        "benchmark_result": str(bench_result),
        "benchmark_window": benchmark_window_payload(benchmark),
        "expected_gpu_count": 1,
        "observed_gpu_count": 1 if gpu else 0,
        "per_gpu_sample_counts": {GPU: len(sequence or ())},
        "per_gpu_max_sample_gap_s": {GPU: largest_gap},
        "metrics": audit_metrics(metrics),
        "cpu_metrics": audit_metrics(cpu_metrics),
    }
    _write_json_atomic(validation_result, validation)
    aggregate = json.loads(agg_result.read_text(encoding="utf-8"))
    if not isinstance(aggregate, dict):
        raise ValueError(f"aggregate is not a JSON object: {agg_result}")
    aggregate = with_power_metrics(
        aggregate,
        metric_keys=WHOLE_METRIC_KEYS,
        schema_version=POWER_METRIC_SCHEMA_VERSION,
        power_valid=not reasons,
        metrics=metrics,
        cpu_power_valid=not reasons,
        cpu_metrics=cpu_metrics,
    )
    aggregate.update(audit_summary(validation, audit_source))
    _write_json_atomic(agg_result, aggregate)
    return not reasons
