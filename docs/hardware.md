# Hardware telemetry (Intel iGPU + NPU)

Targets an **Intel Core Ultra (Meteor Lake / Arrow Lake / Lunar Lake)** class host with an Arc Xe
iGPU and an AI Boost NPU. Both feed the node_exporter **textfile collector** (no privileged
container); a systemd timer runs them every 15s.

## iGPU — `exporters/intel_gpu_textfile.py`
Requires `intel-gpu-tools` (`apt install intel-gpu-tools`). Samples `intel_gpu_top -J` briefly and
emits:
- `intel_gpu_engine_busy_ratio{engine}` — per engine (Render/3D, Blitter, Video, VideoEnhance, Compute)
- `intel_gpu_frequency_mhz{type}` — requested/actual
- `intel_gpu_power_watts{domain}` — GPU/Package
- `intel_gpu_memory_bytes{type=resident|total}` — iGPU memory (summed per-client; integrated GPUs use
  **shared system RAM**, so this is also charged against total RAM in the Host memory breakdown)
- `intel_gpu_clients`, `intel_gpu_rc6_ratio`, `intel_gpu_present`

Safe no-op if the binary or device is absent (`intel_gpu_present 0`).

## Memory breakdown (system + iGPU + NPU)
On this class of SoC the iGPU and NPU **share system RAM**. The Host dashboard shows
`intel_gpu_memory_bytes` and `intel_npu_memory_bytes` as **bytes and % of `node_memory_MemTotal_bytes`**,
plus a stacked "where's my RAM" bar (processes vs iGPU vs NPU vs free). Use `ignoring(type)` /
`scalar()` when dividing the GPU metric (it carries a `type` label) by `node_memory_*`.

## NPU — `exporters/intel_npu_textfile.sh`
Pure sysfs (the `intel_vpu` driver), zero dependencies. Locates the NPU PCI device dynamically and
emits:
- `intel_npu_busy_time_us` (counter → utilization via `rate()`)
- `intel_npu_frequency_mhz{type=current|max}`
- `intel_npu_memory_bytes`, `intel_npu_runtime_active_ms`, `intel_npu_present`

## Install
```bash
sudo apt install -y intel-gpu-tools
sudo cp systemd/accel-textfile.{service,timer} /etc/systemd/system/
sudo systemctl enable --now accel-textfile.timer
```
The node_exporter container mounts the textfile dir read-only; the scripts write world-readable
`.prom` files there.

## Optional: virtualization-host exporter
If the host is a hypervisor, add a host exporter via a **private** compose overlay
(`docker-compose.override.yml`, git-ignored) and a scrape job — kept out of this repo to stay generic.

## NVIDIA dGPU — `exporters/nvidia_gpu_textfile.sh`
For the RTX 3090 eGPU (CUDA inference host). Wraps `nvidia-smi` (driver on the host), `LC_ALL=C` so
awk emits dot decimals, atomic write, safe no-op if `nvidia-smi`/the card is absent. Chained from
`accel_collect.sh` (same `accel-textfile.timer`). Emits (label `gpu`,`name`):
- `nvidia_gpu_utilization_ratio` (0–1), `nvidia_gpu_temperature_celsius`,
  `nvidia_gpu_power_watts` / `nvidia_gpu_power_limit_watts`, `nvidia_gpu_clock_sm_mhz` / `_mem_mhz`
- `nvidia_gpu_memory_{used,free,total}_bytes`
- `nvidia_gpu_process_memory_bytes{pid,process}` — per-process VRAM (e.g. the `llama-server` inference
  process). NB: QMD's embeddings run on the **Intel iGPU** (Vulkan), not the 3090, so they don't appear here.
- `nvidia_gpu_present` (1/0)
Surfaced on the **Accelerators** dashboard (NVIDIA RTX 3090 row). Alerts: `NvidiaVRAMHigh` (>95%, OOM
risk), `NvidiaGPUHot` (>85°C), `NvidiaGPUSaturated`.

## llama.cpp inference metrics
The RTX 3090 inference server (`llama-arc`, llama.cpp `server-cuda`) runs with `--metrics`, exposing
`llamacpp:*` at `:8080/metrics`. Prometheus scrapes it directly over the shared `litellm_default`
network (job `llama-arc`). The **LLM Inference — llama.cpp + MTP** dashboard (ai-agents) shows
decode/prefill tok/s, queue depth, and the **MTP speculative signal**
`llamacpp:tokens_predicted_total / llamacpp:n_decode_total` (≈ tokens accepted per decode; 1.0 = no
speculation, ~2.4 observed with Qwen3.6 MTP). Alerts: `LlamaArcDown`, `LlamaDecodeCollapse`.

**Firewall requirement (important):** node-exporter runs `network_mode: host`, and the dockerised
Prometheus scrapes it via `host.docker.internal:9100`. The host's `INPUT` policy is `DROP`, so
`setup-firewall.sh` must allow it:
`iptables -A INPUT -s 172.16.0.0/12 -p tcp --dport 9100 -j ACCEPT`.
Without that rule the **entire `node` job is down** (no CPU/RAM/disk/iGPU/NPU/NVIDIA metrics) — the
scrape times out (`context deadline exceeded`).
