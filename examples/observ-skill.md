# Example: OpenClaw `observ` cron-agent

A channel-less OpenClaw agent that runs the digest entrypoint on a schedule and reports fleet health.

## 1. Create the agent
```bash
openclaw agents add observ --non-interactive \
  --workspace ~/.openclaw/workspace-observ --model <your-model>
```

## 2. Allowlist the single digest entrypoint (so cron exec needs no approval)
```bash
openclaw approvals allowlist add --agent observ "/opt/observability/onboard/observ-digest.sh"
openclaw approvals allowlist add --agent observ "/usr/bin/curl"
```

## 3. Workspace skill — `~/.openclaw/workspace-observ/skills/observability-onboard/SKILL.md`
```markdown
---
name: observability-onboard
description: Keep observability in sync with the live fleet and report a short digest.
---
Run exactly this allowlisted command and relay its stdout as the digest:

    /opt/observability/onboard/observ-digest.sh

If the output has an `[onboard] NEW:` line, call out the new items first. Read-only otherwise; no
emojis; keep it under ~8 lines. Do not use web_fetch for localhost (private IPs are blocked).
```

## 4. Daily cron
```bash
openclaw cron add "observ-daily-digest" --agent observ --cron "30 8 * * *" \
  --message "Run /opt/observability/onboard/observ-digest.sh and relay its output as today's digest."
```

Add `--announce --channel telegram:<chat-id>` (and bind a Telegram account) to deliver the digest to
your phone. The deterministic `observability-onboard.timer` does the real onboarding every 5 minutes;
this agent adds the human-readable summary.
