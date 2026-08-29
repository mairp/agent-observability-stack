#!/usr/bin/env python3
"""Offline validator for the agents-composite Grafana dashboard.

Usage:
    python3 tools/validate_composite_dashboard.py <path-to-dashboard-json>

Exit 0 iff:
  - JSON parses
  - uid == "agents-composite"
  - $service templating present (Loki label_values, multi + includeAll)
  - every target.expr references service_name
  - no expr contains literal service_name="claude-code"

Exits non-zero with a clear message on any failure.
Pure stdlib — no network, no extra deps.
"""
import json
import re
import sys


def main():
    if len(sys.argv) != 2:
        print("Usage: validate_composite_dashboard.py <dashboard.json>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]

    # 1. Parse JSON
    try:
        with open(path) as f:
            d = json.load(f)
    except FileNotFoundError:
        print(f"FAIL: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"FAIL: JSON parse error: {e}", file=sys.stderr)
        sys.exit(1)

    errors = []

    # 2. Check uid
    if d.get("uid") != "agents-composite":
        errors.append(f"uid is '{d.get('uid')}', expected 'agents-composite'")

    # 3. Check $service templating
    tpl_list = d.get("templating", {}).get("list", [])
    service_var = None
    for v in tpl_list:
        if v.get("name") == "service":
            service_var = v
            break

    if service_var is None:
        errors.append("No 'service' template variable found in templating.list")
    else:
        if service_var.get("type") != "query":
            errors.append(f"service var type is '{service_var.get('type')}', expected 'query'")
        ds = service_var.get("datasource", {})
        if ds.get("type") != "loki":
            errors.append(f"service var datasource type is '{ds.get('type')}', expected 'loki'")
        query = service_var.get("query", "")
        if "label_values(service_name)" not in query:
            errors.append(f"service var query does not contain 'label_values(service_name)': {query!r}")
        if not service_var.get("multi"):
            errors.append("service var multi is not true")
        if not service_var.get("includeAll"):
            errors.append("service var includeAll is not true")

    # 4. Collect every target.expr from every panel
    panels = d.get("panels", [])
    all_exprs = []
    for p in panels:
        for t in p.get("targets", []):
            expr = t.get("expr", "")
            if expr:
                all_exprs.append(expr)

    if not all_exprs:
        errors.append("No targets with expr found in any panel")

    # 5. Every expr must reference service_name
    for i, expr in enumerate(all_exprs):
        if "service_name" not in expr:
            errors.append(f"Panel target expr #{i+1} does not reference service_name: {expr!r}")

    # 6. No expr may hard-code service_name="claude-code"
    for i, expr in enumerate(all_exprs):
        if 'service_name="claude-code"' in expr:
            errors.append(f"Panel target expr #{i+1} hard-codes service_name=\"claude-code\": {expr!r}")
        # Also catch the regex-escaped variant
        if 'service_name=~"claude-code"' in expr:
            errors.append(f"Panel target expr #{i+1} hard-codes service_name=~\"claude-code\": {expr!r}")

    if errors:
        print("FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print("OK: composite dashboard passes all checks")
    sys.exit(0)


if __name__ == "__main__":
    main()
