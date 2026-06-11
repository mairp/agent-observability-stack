.DEFAULT_GOAL := help
SHELL := /bin/bash

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

render: ## Render secrets + templated configs from .env
	@bin/render-secrets.sh

dashboards: ## Regenerate Grafana dashboard JSON
	@python3 bin/gen-dashboards.py

up: render ## Start the stack
	@docker compose up -d

down: ## Stop the stack
	@docker compose down

ps: ## Show stack status
	@docker compose ps

logs: ## Tail stack logs
	@docker compose logs -f --tail=100

reload: ## Hot-reload Prometheus config
	@curl -s -X POST http://127.0.0.1:9090/-/reload && echo reloaded

onboard: ## Run onboarding once
	@set -a; . ./.env; set +a; TEXTFILE_DIR=/var/lib/node_exporter/textfile_collector onboard/observability-onboard.sh

validate: ## Static validation (no running stack)
	@tests/validate.sh

smoke: ## Live smoke test (stack must be up)
	@tests/smoke.sh

test: validate ## Run static validation (alias)

scan: ## Secret scan the public-publishable tree
	@bin/secret-scan.sh

.PHONY: help render dashboards up down ps logs reload onboard validate smoke test scan
