#!/usr/bin/env bash

set -o pipefail
repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
source "$repo_root/benchmarks/check_env.sh"
check_env_vars OUT_YAML

# Not measured here: the curve was measured outside Actions, and this run gives it the
# source_run every curve must name.
curve="$repo_root/infx/golden_al_distribution/qwen3.8-27b-nvfp4__mtp__native__default-default.yaml"
# speedbench-al.yml adds source_run and the collection block itself.
awk '/^# SPEED-Bench client settings/ { exit } !/^source_run:/' "$curve" > "$OUT_YAML"
cat "$OUT_YAML"
