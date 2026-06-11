#!/usr/bin/env bash
# QMD (RAG) index health -> Prometheus textfile collector.
# Reports doc/vector counts, index size, and freshness (age) per configured index.
# Configure indexes via QMD_INDEXES="name:cacheDir:configDir,name2:...". Defaults target the
# common OpenClaw/Claude memory layout; missing indexes are skipped silently.
set -uo pipefail
OUT="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile_collector}/qmd.prom"
NOW=$(date +%s)

DEFAULT_INDEXES="claude:${HOME}/.claude/qmd/xdg-cache:${HOME}/.claude/qmd/xdg-config"
DEFAULT_INDEXES+=",openclaw-main:${HOME}/.openclaw/agents/main/qmd/xdg-cache:${HOME}/.openclaw/agents/main/qmd/xdg-config"
DEFAULT_INDEXES+=",openclaw-havan:${HOME}/.openclaw/agents/havan/qmd/xdg-cache:${HOME}/.openclaw/agents/havan/qmd/xdg-config"
INDEXES="${QMD_INDEXES:-$DEFAULT_INDEXES}"

tmp="$(mktemp)"
{
  echo "# HELP qmd_documents_total Documents indexed in a QMD RAG index."
  echo "# TYPE qmd_documents_total gauge"
  echo "# HELP qmd_vectors_total Embedded vectors in a QMD RAG index."
  echo "# TYPE qmd_vectors_total gauge"
  echo "# HELP qmd_index_size_bytes On-disk size of a QMD index."
  echo "# TYPE qmd_index_size_bytes gauge"
  echo "# HELP qmd_index_age_seconds Seconds since the QMD index was last updated (freshness)."
  echo "# TYPE qmd_index_age_seconds gauge"
  IFS=','; for entry in $INDEXES; do
    IFS=':' read -r name cache cfg <<< "$entry"
    idx="$cache/qmd/index.sqlite"
    [ -f "$idx" ] || continue
    out="$(XDG_CACHE_HOME="$cache" XDG_CONFIG_HOME="$cfg" qmd status 2>/dev/null)"
    docs="$(printf '%s' "$out" | awk '/Total:/{print $2; exit}')"
    vecs="$(printf '%s' "$out" | awk '/Vectors:/{print $2; exit}')"
    size="$(stat -c %s "$idx" 2>/dev/null || echo 0)"
    mtime="$(stat -c %Y "$idx" 2>/dev/null || echo "$NOW")"
    [ -n "$docs" ] && echo "qmd_documents_total{index=\"$name\"} $docs"
    [ -n "$vecs" ] && echo "qmd_vectors_total{index=\"$name\"} $vecs"
    age=$((NOW - mtime)); [ "$age" -lt 0 ] && age=0
    echo "qmd_index_size_bytes{index=\"$name\"} $size"
    echo "qmd_index_age_seconds{index=\"$name\"} $age"
  done
} > "$tmp"
mv "$tmp" "$OUT"; chmod 644 "$OUT"
