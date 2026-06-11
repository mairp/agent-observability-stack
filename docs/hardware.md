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
