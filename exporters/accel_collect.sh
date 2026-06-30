#!/usr/bin/env bash
# Run the accelerator collectors (Intel NPU + iGPU, NVIDIA dGPU) into the node-exporter textfile dir.
set -uo pipefail
export TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}"
HERE="$(dirname "$(readlink -f "$0")")"
"$HERE/intel_npu_textfile.sh" || true
"$HERE/intel_gpu_textfile.py" || true
"$HERE/nvidia_gpu_textfile.sh" || true
"$HERE/openclaw_textfile.sh" || true
"$HERE/qmd_textfile.sh" || true
