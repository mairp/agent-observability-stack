#!/usr/bin/env bash
# NVIDIA GPU (RTX 3090 eGPU) -> Prometheus textfile collector.
# Wraps `nvidia-smi` (driver lives on the Proxmox host). Mirrors the Intel collectors:
# atomic write via mktemp+mv, safe no-op if nvidia-smi/the card is absent.
set -uo pipefail
# Force C locale: nvidia-smi is fine, but awk's printf %g would otherwise emit comma
# decimals under the host's locale (e.g. "33,42"), which is invalid Prometheus syntax.
export LC_ALL=C LANG=C

OUT="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}/nvidia_gpu.prom"
MIB=1048576

tmp="$(mktemp)"
{
  echo "# HELP nvidia_gpu_present Whether nvidia-smi produced a sample."
  echo "# TYPE nvidia_gpu_present gauge"

  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia_gpu_present 0"
  else
    # Per-GPU: one CSV row per card. nounits -> util %, memory MiB, power W, clocks MHz.
    rows="$(nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.free,memory.total,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem \
              --format=csv,noheader,nounits 2>/dev/null)"
    if [ -z "$rows" ]; then
      echo "nvidia_gpu_present 0"
    else
      echo "nvidia_gpu_present 1"
      echo "# HELP nvidia_gpu_utilization_ratio GPU compute utilization (0-1)."
      echo "# TYPE nvidia_gpu_utilization_ratio gauge"
      echo "# HELP nvidia_gpu_memory_used_bytes Frame-buffer memory in use."
      echo "# TYPE nvidia_gpu_memory_used_bytes gauge"
      echo "# HELP nvidia_gpu_memory_free_bytes Frame-buffer memory free."
      echo "# TYPE nvidia_gpu_memory_free_bytes gauge"
      echo "# HELP nvidia_gpu_memory_total_bytes Total frame-buffer memory."
      echo "# TYPE nvidia_gpu_memory_total_bytes gauge"
      echo "# HELP nvidia_gpu_temperature_celsius GPU core temperature."
      echo "# TYPE nvidia_gpu_temperature_celsius gauge"
      echo "# HELP nvidia_gpu_power_watts Current board power draw."
      echo "# TYPE nvidia_gpu_power_watts gauge"
      echo "# HELP nvidia_gpu_power_limit_watts Enforced board power limit."
      echo "# TYPE nvidia_gpu_power_limit_watts gauge"
      echo "# HELP nvidia_gpu_clock_sm_mhz SM (compute) clock."
      echo "# TYPE nvidia_gpu_clock_sm_mhz gauge"
      echo "# HELP nvidia_gpu_clock_mem_mhz Memory clock."
      echo "# TYPE nvidia_gpu_clock_mem_mhz gauge"

      # Parse each GPU row.
      echo "$rows" | while IFS=, read -r idx name util mused mfree mtotal temp pdraw plimit csm cmem; do
        # trim leading spaces
        idx="${idx# }"; name="${name# }"; util="${util# }"; mused="${mused# }"; mfree="${mfree# }"
        mtotal="${mtotal# }"; temp="${temp# }"; pdraw="${pdraw# }"; plimit="${plimit# }"; csm="${csm# }"; cmem="${cmem# }"
        g="gpu=\"${idx}\",name=\"${name}\""
        awk -v g="$g" -v u="$util" -v mu="$mused" -v mf="$mfree" -v mt="$mtotal" \
            -v t="$temp" -v pd="$pdraw" -v pl="$plimit" -v cs="$csm" -v cm="$cmem" -v MIB="$MIB" 'BEGIN{
          if (u  ~ /^[0-9.]+$/) printf "nvidia_gpu_utilization_ratio{%s} %g\n", g, u/100
          if (mu ~ /^[0-9.]+$/) printf "nvidia_gpu_memory_used_bytes{%s} %.0f\n", g, mu*MIB
          if (mf ~ /^[0-9.]+$/) printf "nvidia_gpu_memory_free_bytes{%s} %.0f\n", g, mf*MIB
          if (mt ~ /^[0-9.]+$/) printf "nvidia_gpu_memory_total_bytes{%s} %.0f\n", g, mt*MIB
          if (t  ~ /^[0-9.]+$/) printf "nvidia_gpu_temperature_celsius{%s} %g\n", g, t
          if (pd ~ /^[0-9.]+$/) printf "nvidia_gpu_power_watts{%s} %g\n", g, pd
          if (pl ~ /^[0-9.]+$/) printf "nvidia_gpu_power_limit_watts{%s} %g\n", g, pl
          if (cs ~ /^[0-9.]+$/) printf "nvidia_gpu_clock_sm_mhz{%s} %g\n", g, cs
          if (cm ~ /^[0-9.]+$/) printf "nvidia_gpu_clock_mem_mhz{%s} %g\n", g, cm
        }'
      done

      # Per-process VRAM (splits llama-server vs the QMD `node` process, etc.).
      apps="$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits 2>/dev/null)"
      if [ -n "$apps" ]; then
        echo "# HELP nvidia_gpu_process_memory_bytes Per-process GPU memory use."
        echo "# TYPE nvidia_gpu_process_memory_bytes gauge"
        echo "$apps" | while IFS=, read -r pid pname pmem; do
          pid="${pid# }"; pname="${pname# }"; pmem="${pmem# }"
          # base name only (e.g. /app/llama-server -> llama-server)
          pname="${pname##*/}"
          [ "$pmem" -eq "$pmem" ] 2>/dev/null || continue
          awk -v pid="$pid" -v pn="$pname" -v m="$pmem" -v MIB="$MIB" 'BEGIN{
            printf "nvidia_gpu_process_memory_bytes{pid=\"%s\",process=\"%s\"} %.0f\n", pid, pn, m*MIB
          }'
        done
      fi
    fi
  fi
} > "$tmp"
mv "$tmp" "$OUT"
chmod 644 "$OUT"
