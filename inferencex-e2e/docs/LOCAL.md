# InferenceX-local

InferenceX-local is the fork of [InferenceX](https://github.com/SemiAnalysisAI/InferenceX) for
local hardware. This guide holds what differs from upstream; the upstream guides apply unchanged
otherwise.

## Staying in sync with InferenceX

Upstream lands many commits a day, and a merge of its `main` stays clean only while this repository
changes few files that upstream also has. A change goes, in order of preference, into:

1. A new file. Upstream does not have the path, so it cannot conflict. Local benchmark configs go
   in [`configs/local-master.yaml`](../configs/local-master.yaml), local documentation in this guide,
   and tests of local code in their own test files.
2. A file this repository owns: `inferencex-e2e/perf-changelog.yaml` and `.github/CODEOWNERS`.
   Upstream has both, but [`.gitattributes`](../../.gitattributes) makes a merge keep the copy here.
   Upstream's changelog entries therefore never arrive, and a merge starts no sweep or ingest.
3. An upstream file, when nothing else works: an entry in a registry that has one file, or a change
   that lets core code be extended. Put a registry entry at the head of its section, as upstream
   appends at the tail, and offer a core change to upstream.

To merge upstream:

```bash
git config merge.ours.driver true
git fetch https://github.com/SemiAnalysisAI/InferenceX.git main
git checkout -b sync/upstream origin/main
git merge --no-ff FETCH_HEAD
```

Open a pull request from that branch and merge it with a merge commit. A squash or rebase drops the
merge parent, and the next merge then conflicts with every change in this one.

## Benchmark configs

Local hardware has one master config, [`configs/local-master.yaml`](../configs/local-master.yaml),
with the fields [CONFIGS.md](../configs/CONFIGS.md) describes. Its SKU is `gb10` (DGX Spark).

## Models

| Model | Prefix | Date added | Active scenarios |
|---|---|---|---|
| Qwen3.8-27B | `qwen3.827b` | 2026-10-27 | Agentic coding (vLLM with native MTP on the DGX Spark; golden AL curve [`qwen3.8-27b-nvfp4__mtp__native__default-default.yaml`](../infx/golden_al_distribution/qwen3.8-27b-nvfp4__mtp__native__default-default.yaml)) |
| Qwen3.8-Flash-Next | `qwen3.8next` | 2026-08-26 ([upstream #2742](https://github.com/SemiAnalysisAI/InferenceX/pull/2742)) | Agentic coding (SGLang with native MTP on the DGX Spark) |

Qwen3.8-27B's primary engine is upstream vLLM. Its agreed draft model (PoR) is TBD; the
one proposed, pending partner alignment, is native MTP (golden AL collector:
[`qwen3.827b_fp4_b300_vllm.sh`](../benchmarks/single_node/speedbench/qwen3.827b_fp4_b300_vllm.sh)).
AgentX replays the 256k-capped corpus for `qwen3.827b`, as it does for `qwen3.8next`.

## Golden acceptance curves

A [golden acceptance curve](../infx/golden_al_distribution/README.md) records the
`speedbench-al.yml` run that measured it as its `source_run`. Upstream dispatches that workflow on
a B300. Here it may run on any local runner that serves the model with real speculative decoding,
by passing that runner's label as `runner`, and the `source_run` is the run in this repository.
The machine doesn't change the curve: Qwen3.8-27B NVFP4 measured on a DGX Spark and on a B300
agreed to within 2% with thinking on and 5% with thinking off.

A curve measured outside Actions gets its `source_run` from a run of its collector's `recorded`
variant (`collector-variant=recorded`), which returns the committed curve without measuring it,
until a measuring run replaces it.

The workflow asks for a B300's 8 GPUs and gets the ones the node has. It looks for the collector
under upstream's `<model-prefix>_fp4_b300_<framework>.sh` name on every machine. The runner's
cluster needs an `hf-home` volume, and either the model in its `models.entries` or a
`models.download-root` for the collector to download into.

## Runner setup

[RUNNER_SETUP.md](../utils/runner_setup/RUNNER_SETUP.md) describes the runners of a Slurm cluster.
Local hosts differ as follows.

### DGX Spark

A DGX Spark (`gb10-spark`) runs that setup with `munge`, `slurmctld` and `slurmd` on the host
beside its runner. The host hangs rather than OOM-killing when its unified memory runs out, so cap
jobs at 116 GiB of the DGX Spark's available 121.6 GiB with `MemSpecLimit`. That cap doesn't count
GPU allocations, so recipes must also leave room. Enroot's `/tmp` is a tmpfs in that memory, so the
[cluster profile](../configs/runners.yaml) points `TMPDIR` at `/var/tmp`. Load Pyxis with
`container_scope=job` so a job's root filesystem is removed when it ends. On Ubuntu 24.04,
`enroot-nsenter` needs the AppArmor profile the enroot package installs to create user namespaces.
