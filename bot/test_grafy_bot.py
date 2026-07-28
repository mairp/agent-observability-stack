"""Hermetic pytest suite for grafy_bot — composite + Loki value path.

No real network: all HTTP is monkeypatched/faked.
"""
import json
import os
import socket
import pytest
import requests

# Set required env vars BEFORE importing grafy_bot
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("TELEGRAM_ALLOWED_CHATS", "12345")
os.environ.setdefault("GRAFANA_URL", "http://grafana:3000")
os.environ.setdefault("GRAFANA_USER", "admin")
os.environ.setdefault("GRAFANA_PASSWORD", "admin")
os.environ.setdefault("PROM_URL", "http://prometheus:9090")
os.environ.setdefault("GRAFANA_PUBLIC_URL", "")
os.environ.setdefault("RENDER_WIDTH", "1600")
os.environ.setdefault("RENDER_HEIGHT", "1300")
os.environ.setdefault("LOKI_URL", "http://loki:3100")


# ---------------------------------------------------------------------------
# Helpers — patch the *global* requests module with a FakeSession.
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, json_data, status_code=200, headers=None):
        self.json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.json_data


class FakeSession:
    """A requests-like object that never opens a real socket."""

    def __init__(self):
        self._calls = []
        self._handlers = {}

    def set_handler(self, pattern, response):
        """Register a handler for URLs matching pattern."""
        self._handlers[pattern] = response

    def _make_call(self, method, url, **kwargs):
        self._calls.append((method, url, kwargs))
        for pattern, resp in self._handlers.items():
            if pattern in url:
                if callable(resp):
                    return resp(url, **kwargs)
                return FakeResponse(resp) if isinstance(resp, dict) else resp
        return FakeResponse({"error": "no handler"}, 404)

    def get(self, url, **kwargs):
        return self._make_call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._make_call("POST", url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._make_call(method, url, **kwargs)

    @property
    def total_calls(self):
        return len(self._calls)


def _patch_requests(monkeypatch):
    """Patch the global requests module with a fresh FakeSession."""
    sess = FakeSession()
    monkeypatch.setattr(requests, "get", sess.get)
    monkeypatch.setattr(requests, "post", sess.post)
    monkeypatch.setattr(requests, "request", sess.request)
    return sess


# ---------------------------------------------------------------------------
# Test: lokiq() parses a mocked Loki scalar
# ---------------------------------------------------------------------------

class TestLokiq:
    def test_lokiq_scalar(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        sess.set_handler(
            "/loki/api/v1/query",
            {"data": {"result": [{"metric": {}, "value": ["1700000000000", "42.5"]}]}}
        )

        result = grafy.lokiq('{service_name=~"$service"} | event_name=`api_request`')
        assert result == "42.5"
        assert sess.total_calls == 1  # exactly one HTTP call

    def test_lokiq_empty_result(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        sess.set_handler(
            "/loki/api/v1/query",
            {"data": {"result": []}}
        )

        result = grafy.lokiq('nonexistent_expr')
        assert result is None

    def test_lokiq_connection_error(self, monkeypatch):
        import bot.grafy_bot as grafy

        # Replace get to raise an exception
        orig_get = requests.get
        requests.get = lambda *a, **kw: (_ for _ in ()).throw(socket.error("no network"))

        try:
            result = grafy.lokiq('bad')
            assert result is None  # should not raise
        finally:
            requests.get = orig_get


# ---------------------------------------------------------------------------
# Test: composite SUMMARY routes to Loki and renders both services
# ---------------------------------------------------------------------------

class TestCompositeSummary:
    def test_composite_values_text_loki(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        def loki_handler(url, **kw):
            return FakeResponse({
                "data": {"result": [{"metric": {}, "value": ["1700000000000", "123.45"]}]}
            })

        sess.set_handler("/loki/api/v1/query", loki_handler)

        text = grafy.values_text("agents-composite")
        assert "CC cost 24h" in text
        assert "CC tokens 24h" in text
        assert "CC cache-read" in text
        assert "CC requests" in text
        assert "123.45" in text
        # All calls should go to Loki for composite
        for call_method, call_url, _ in sess._calls:
            assert "loki" in call_url or call_method != "GET"

    def test_composite_summary_contains_both_services(self, monkeypatch):
        """The composite SUMMARY should carry values for both claude-code and pi."""
        import bot.grafy_bot as grafy

        rows = grafy.SUMMARY.get("agents-composite", [])
        assert len(rows) > 0
        for row in rows:
            assert len(row) >= 4
            assert row[3] in ("loki", "prom")
            if row[0].startswith("CC "):
                assert row[3] == "loki"


# ---------------------------------------------------------------------------
# Test: existing prom-sourced dashboard rows still render
# ---------------------------------------------------------------------------

class TestExistingPromDashboards:
    def test_host_dashboard_still_works(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        def prom_handler(url, **kw):
            return FakeResponse({
                "data": {"result": [{"metric": {}, "value": ["1700000000000", "73.2"]}]}
            })

        sess.set_handler("/api/v1/query", prom_handler)

        text = grafy.values_text("host")
        assert "CPU busy" in text
        assert "73.2" in text

    def test_claude_code_dashboard_still_works(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        def prom_handler(url, **kw):
            return FakeResponse({
                "data": {"result": [{"metric": {}, "value": ["1700000000000", "42"]}]}
            })

        sess.set_handler("/api/v1/query", prom_handler)

        text = grafy.values_text("claude-code")
        assert "CC tokens 24h" in text
        assert "CC cost 24h" in text


# ---------------------------------------------------------------------------
# Test: no real socket opened during tests
# ---------------------------------------------------------------------------

class TestNoRealNetwork:
    def test_lokiq_uses_fake_session(self, monkeypatch):
        """Verify that lokiq() goes through our fake session, not real network."""
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        sess.set_handler(
            "/loki/api/v1/query",
            {"data": {"result": [{"metric": {}, "value": ["1700000000000", "0"]}]}},
        )

        grafy.lokiq("test")
        assert sess.total_calls == 1

    def test_promq_uses_fake_session(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy

        sess.set_handler(
            "/api/v1/query",
            {"data": {"result": [{"metric": {}, "value": ["1700000000000", "0"]}]}},
        )

        grafy.promq("test")
        assert sess.total_calls == 1


# ---------------------------------------------------------------------------
# Test: DASH aliases include composite
# ---------------------------------------------------------------------------

class TestDashAliases:
    def test_composite_aliases(self, monkeypatch):
        """Verify the composite aliases exist in DASH."""
        import bot.grafy_bot as grafy

        for alias in ("composite", "agents-composite", "both", "claude-vs-pi"):
            assert alias in grafy.DASH, f"Missing alias: {alias}"
            uid, slug, title = grafy.DASH[alias]
            assert uid == "agents-composite"
            assert slug == "agents-composite"
            assert title == "Agents — Claude Code vs pi"

    def test_existing_dashboards_untouched(self, monkeypatch):
        """Ensure existing dashboard aliases are still present."""
        import bot.grafy_bot as grafy

        assert "host" in grafy.DASH
        assert "claude-code" in grafy.DASH
        assert "agents" in grafy.DASH
        assert "llm-cost" in grafy.DASH
        assert grafy.DASH["host"][0] == "host"
        assert grafy.DASH["claude-code"][0] == "claude-code"

    def test_ralph_aliases(self, monkeypatch):
        """Ralph loop dashboard is reachable by curated aliases."""
        import bot.grafy_bot as grafy

        for alias in ("ralph", "ralph-loops", "loops", "loop"):
            assert alias in grafy.DASH, f"Missing alias: {alias}"
            uid, slug, title = grafy.DASH[alias]
            assert uid == "ralph-loops"
            assert slug == "ralph-loops"
            assert "Ralph" in title

    def test_ralph_summary_is_loki(self, monkeypatch):
        """The ralph-loops SUMMARY must query Loki (Ralph telemetry lives there)."""
        import bot.grafy_bot as grafy

        rows = grafy.SUMMARY.get("ralph-loops", [])
        assert len(rows) > 0
        for row in rows:
            assert len(row) >= 4 and row[3] == "loki"


# ---------------------------------------------------------------------------
# Test: dynamic Grafana discovery — new dashboards resolve without code changes
# ---------------------------------------------------------------------------

_SEARCH = [
    {"uid": "ralph-loops", "title": "Ralph Loops (Claude Code)", "url": "/d/ralph-loops/ralph-loops"},
    {"uid": "brand-new", "title": "Brand New Board", "url": "/d/brand-new/brand-new-board"},
]


class TestDiscovery:
    def _fresh(self, monkeypatch):
        sess = _patch_requests(monkeypatch)
        import bot.grafy_bot as grafy
        # reset the module-level cache so each test starts cold
        grafy._disco.update(at=0.0, by_uid={}, by_key={})
        sess.set_handler("/api/search", FakeResponse(_SEARCH))
        return sess, grafy

    def test_grafana_search_parses(self, monkeypatch):
        _, grafy = self._fresh(monkeypatch)
        found = grafy.grafana_search()
        uids = {u for u, _s, _t in found}
        assert uids == {"ralph-loops", "brand-new"}
        # slug is pulled from the /d/<uid>/<slug> url
        assert dict((u, s) for u, s, _ in found)["brand-new"] == "brand-new-board"

    def test_resolve_finds_new_dashboard_by_uid(self, monkeypatch):
        _, grafy = self._fresh(monkeypatch)
        d = grafy.resolve("brand-new")
        assert d is not None and d[0] == "brand-new"
        assert d[1] == "brand-new-board"

    def test_resolve_finds_new_dashboard_by_title_word(self, monkeypatch):
        _, grafy = self._fresh(monkeypatch)
        # "board" is a significant word from the title -> resolves to the uid
        d = grafy.resolve("board")
        assert d is not None and d[0] == "brand-new"

    def test_curated_wins_over_discovery(self, monkeypatch):
        """A curated alias must never be shadowed by discovery."""
        _, grafy = self._fresh(monkeypatch)
        d = grafy.resolve("host")
        assert d == grafy.DASH["host"]

    def test_discovery_cache_survives_transient_failure(self, monkeypatch):
        sess, grafy = self._fresh(monkeypatch)
        grafy.discover(force=True)                       # warm cache
        assert "brand-new" in grafy._disco["by_uid"]
        sess.set_handler("/api/search", FakeResponse([], 500))  # now search fails
        by_uid = grafy.discover(force=True)
        assert "brand-new" in by_uid                     # last good snapshot retained

    def test_unknown_still_unresolved(self, monkeypatch):
        _, grafy = self._fresh(monkeypatch)
        assert grafy.resolve("does-not-exist-anywhere") is None
