# Host-local scrape jobs

`prometheus.yml` loads every `*.yml` here through `scrape_config_files`. The `*.yml` files are
gitignored: put scrape jobs that name this host (a hypervisor exporter, LAN-only targets) here,
so the committed configuration stays generic. Each file holds a top-level `scrape_configs:` list.
