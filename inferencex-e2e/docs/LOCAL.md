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
with the fields [CONFIGS.md](../configs/CONFIGS.md) describes. Its SKUs are `gb10` (DGX Spark) and
`m5ultra`. `framework` may also be `llamacpp`.

A cluster record in [`configs/runners.yaml`](../configs/runners.yaml) also has:

- `arch` (`x86_64` or `aarch64`) and `os` (`linux`, the default, or `darwin`) describe the
  cluster's hosts.
- `scheduler: native` runs jobs as processes on the launching host, with its settings under
  `native:`; see [Native clusters](#native-clusters).
- A cluster without an srt-slurm profile, on any scheduler, runs single-node points through
  [the serve path](#the-serve-path) and refuses multi-node ones.

### Native clusters

A cluster with `scheduler: native` has no job scheduler and no containers: each job runs as a
process group on the runner host, in the checkout. Elsewhere in this repository "native" keeps
upstream's other meanings, such as a model's own MTP head (native MTP) and srt-slurm's native launch
path and power telemetry. The cluster's `native:` record
([`infx/clusters/native.py`](../infx/clusters/native.py)) holds its volumes, which are host `path`s,
and `root`, a host directory for unpacked images and job records. An `image` is a tar archive pinned
by digest, `<archive url>@sha256:<hex>`, that unpacks to one directory, which goes last on the job's
`PATH`, after the clients' packages and the system's commands.
An argument or environment value that is one absolute container path is rewritten to the host
path behind it; a path inside a longer value, such as `--log=/workspace/x`, is not. A host runs
one native job at a time, and `python -m infx.launch cleanup` stops one an earlier launch left
running. The digest only proves an archive is the one a reviewer pinned, not that it is safe.
Nothing isolates a job from the runner account, so give that account nothing else to hold and
review a new archive as you would code. The job's clients run with the packages
[`native-client/`](../native-client/pyproject.toml) pins, in a lock of its own so that an upstream
dependency bump does not change them.

### The serve path

A cluster without an srt-slurm profile runs single-node AgentX points through the launcher's serve
path ([`infx/launch/drivers/serve.py`](../infx/launch/drivers/serve.py)), which has a server for
`llamacpp` and refuses other frameworks and fixed-sequence points. The point's `srt-recipe` variant
is bound and validated as for srt-slurm, without its power telemetry. One job then starts the
framework's server from the bound `roles.agg` args and runs the AgentX client and any eval.

A recipe may set only the fields in `RECIPE_FIELDS`; the path also refuses `REQUIRE_POWER` on a
point that records no power (any point off a Mac, and an eval-only point on one), `'@fabric.<name>'`
values, a point's own `MODEL_PATH`, and server args the launcher sets (`LAUNCHER_ARGS`). The server
has `health_check`'s `max_attempts` x
`interval_seconds` to become ready, 180 x 10 s by default. The cluster needs an `hf-hub-cache`
volume, mounted at `HF_HUB_CACHE`, and serves a staged `models.entries` checkpoint when it has one.

On a cluster with `os: darwin`, an AgentX point records its power automatically.
`python3 -m infx.bench.powermetrics` samples GPU, CPU and ANE power about once a second, and the
launcher joins the samples to the benchmark window, writing the metrics to the result and a
`power_validation_<result>.json` sidecar. The power and energy-per-token metrics are the GPU's, as
upstream's are. The CPU's power and the whole chip's (CPU, GPU and ANE) are published beside them
as upstream's CPU socket and module metrics. The runner account needs passwordless
`sudo` for `/usr/bin/powermetrics`. Invalid samples record `power_valid: 0`, and fail the point
only under `REQUIRE_POWER=1`. The `power_audit_<result>` artifact of a Mac job holds `windows/` and
a `samples.csv` of `timestamp_unix,combined_w,cpu_w,gpu_w,ane_w`.

A `llamacpp` point serves `llama-server` from a staged checkpoint. Its recipe names the GGUF file
as `roles.agg.args.model`, a path inside the checkpoint (the first file of a split one), and sets
`lazy-mode` and `flash-attn` to the string `on`, `off` or `auto`. Without a unified KV cache each
of the `parallel` slots has `ctx-size / parallel` tokens. An MTP recipe sets `spec-type: draft-mtp`,
`spec-draft-n-max` and, for a checkpoint with no embedded head, `model-draft`, the head's path
inside the checkpoint. The launcher pins an AgentX point to the golden acceptance length with
`spec-synth-len`; an eval-only point keeps its real acceptance and first runs the report-only
[speculative acceptance gate](../infx/evals/EVALS.md#speculative-acceptance-gate).

## Models

| Model | Prefix | Date added | Active scenarios |
|---|---|---|---|
| Qwen3.8-27B | `qwen3.827b` | 2026-10-27 | Agentic coding (vLLM with native MTP on the DGX Spark, golden AL curve [`qwen3.8-27b-nvfp4__mtp__native__default-default.yaml`](../infx/golden_al_distribution/qwen3.8-27b-nvfp4__mtp__native__default-default.yaml); llama.cpp without MTP on the M5 Ultra) |
| Qwen3.8-Flash-Next | `qwen3.8next` | 2026-08-26 ([upstream #2742](https://github.com/SemiAnalysisAI/InferenceX/pull/2742)) | Agentic coding (SGLang with native MTP on the DGX Spark; llama.cpp without MTP on the M5 Ultra) |

Qwen3.8-27B's primary engine is upstream vLLM. Its agreed draft model (PoR) is TBD; the
one proposed, pending partner alignment, is native MTP (golden AL collector:
[`qwen3.827b_fp4_b300_vllm.sh`](../benchmarks/single_node/speedbench/qwen3.827b_fp4_b300_vllm.sh)).
Both models run llama.cpp on the M5 Ultra, as Apple silicon runs neither vLLM nor SGLang. AgentX
replays the 256k-capped corpus for `qwen3.827b`, as it does for `qwen3.8next`.

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

## llama.cpp

Recipes live under the `llamacpp` engine directory. The planner's parallelism check
([RECIPES.md](../benchmarks/multi_node/srt-slurm-recipes/RECIPES.md)) compares a llama.cpp recipe
with a `tp` that is always 1; `ep` must be 1 and `dp-attn` false.

llama.cpp supports synthetic acceptance through `llama-server --spec-synth-len`, which takes the
golden AL directly:

```bash
llama-server \
  --model MODEL.gguf \
  --model-draft MTP_HEAD.gguf \
  --spec-type draft-mtp \
  --spec-draft-n-max 3 \
  --spec-synth-len 2.48
```

srtctl runs no llama.cpp, so the launcher's [serve driver](../infx/launch/drivers/serve.py), not the
connector, sets this flag for a role with `spec-type: draft-mtp`, and it refuses a recipe that sets
`spec-synth-len` or `spec-synth-rates`.

On the serve path, one job serves the point, so `infx.bench serve` runs `al-gate` itself once
the server is ready and before the eval. It stops the gate's process group after
`AL_GATE_TIMEOUT_S` and ignores its status, as the shim does. llama-server exports the counters as
`llamacpp:spec_decode_num_accepted_tokens_total` and `llamacpp:spec_decode_num_drafts_total`.

The sign-off facts resolve a native image by an HTTP HEAD of its archive URL, without the
`@sha256:` digest, where they run `docker manifest inspect` for a container image.

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

### Apple silicon hosts without a container runtime (`scheduler: native`)

A Mac runs its runner and each benchmark on the host, under the runner account (see
[Native clusters](#native-clusters)). The Slurm setup assumes Linux and tmux; on the Mac:

1. Create a standard (non-admin) macOS user for the runner. It owns `native.root` and the volumes,
   including the staged GGUFs. Run nothing else on the host while it serves.
2. As an administrator, run `xcode-select --install`, for `git` and `/usr/bin/python3`, and give the
   account passwordless `sudo` for `/usr/bin/powermetrics`, which
   [records power](#the-serve-path).
3. As the account, run `setup.sh` as that guide describes, with indices `0 0` and the macOS ARM64
   tarball from
   [the new runner page](https://github.com/SemiAnalysisAI/InferenceX-local/settings/actions/runners/new?arch=arm64&os=osx),
   for example named `m5ultra-exo` with tag `cluster:m5ultra-exo`. Register only one runner per
   host: a second would fail the jobs it picks up.
4. Run `./svc.sh install && ./svc.sh start` in `~/gharunners/gharunner00/actions-runner`. The launch
   agent this installs starts only when the account logs in, so either log in automatically at boot
   (FileVault must be off) or have an administrator install the same plist under
   `/Library/LaunchDaemons` with `UserName` set to the account. Check that the plist sets
   `ProcessType` to `Interactive`: launchd throttles a job without it, which skews benchmarks.
5. As an administrator, run `sudo pmset -a sleep 0 disksleep 0 powernap 0` to keep the Mac awake and
   `sudo pmset -a autorestart 1` to restart it after a power failure.
6. A launch run by hand needs `uv` on its `PATH` (CI installs it). To recover by hand, run
   `python -m infx.launch cleanup` with `RUNNER_NAME` set, as the account.

A `native` cluster names its storage paths in `native.volumes`. Allow about 7 GB under
`native.root` for a running AgentX job.
