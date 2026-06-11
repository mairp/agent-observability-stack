#!/usr/bin/env bash
# Intel NPU (AI Boost / VPU) -> Prometheus textfile collector.
# Reads sysfs counters exposed by the intel_vpu driver. No external tools needed.
set -euo pipefail

OUT="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}/intel_npu.prom"
# Locate the NPU PCI device dynamically (driver: intel_vpu).
DEV="$(readlink -f /sys/bus/pci/drivers/intel_vpu/0000:* 2>/dev/null | head -1 || true)"
[ -z "${DEV:-}" ] && DEV="$(for d in /sys/devices/pci0000:00/*/npu_busy_time_us; do dirname "$d"; break; done 2>/dev/null || true)"

tmp="$(mktemp)"
{
  echo "# HELP intel_npu_present Whether an Intel NPU device was found."
  echo "# TYPE intel_npu_present gauge"
  if [ -n "${DEV:-}" ] && [ -d "$DEV" ]; then
    echo "intel_npu_present 1"
    r() { [ -r "$DEV/$1" ] && cat "$DEV/$1" 2>/dev/null || echo ""; }
    busy=$(r npu_busy_time_us);   cur=$(r npu_current_frequency_mhz)
    max=$(r npu_max_frequency_mhz); mem=$(r npu_memory_utilization)
    ract=$(r power/runtime_active_time); rsus=$(r power/runtime_suspended_time)
    [ -n "$busy" ] && { echo "# TYPE intel_npu_busy_time_us counter"; echo "intel_npu_busy_time_us $busy"; }
    [ -n "$cur" ]  && { echo "# TYPE intel_npu_frequency_mhz gauge"; echo "intel_npu_frequency_mhz{type=\"current\"} $cur"; }
    [ -n "$max" ]  &&   echo "intel_npu_frequency_mhz{type=\"max\"} $max"
    [ -n "$mem" ]  && { echo "# TYPE intel_npu_memory_bytes gauge"; echo "intel_npu_memory_bytes $mem"; }
    [ -n "$ract" ] && { echo "# TYPE intel_npu_runtime_active_ms counter"; echo "intel_npu_runtime_active_ms $ract"; }
    [ -n "$rsus" ] && { echo "# TYPE intel_npu_runtime_suspended_ms counter"; echo "intel_npu_runtime_suspended_ms $rsus"; }
  else
    echo "intel_npu_present 0"
  fi
} > "$tmp"
mv "$tmp" "$OUT"
chmod 644 "$OUT"
