import pytest

from autoearn.adapters import AdapterManifest, AdapterRegistry, DiscoveredLead
from autoearn.adapter_runtime import AdapterRateLimitError, DiscoveryRuntime


class CountingAdapter:
    def __init__(self, *, limit=2, fail=False):
        self.calls = 0
        self.fail = fail
        self.manifest = AdapterManifest(
            adapter_id="counting",
            display_name="Counting source",
            categories=("other",),
            allowed_domains=("example.com",),
            requests_per_minute=limit,
        )

    def discover(self):
        self.calls += 1
        if self.fail:
            raise TimeoutError("upstream unavailable")
        return [
            DiscoveredLead(
                title="Public opportunity",
                url="https://example.com/opportunity/1",
                category="other",
                source_name="Counting source",
                observed_at="2026-11-17T10:00:00+00:00",
            )
        ]


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def setup_runtime(adapter, *, ttl=30):
    registry = AdapterRegistry()
    registry.register(adapter)
    clock = FakeClock()
    runtime = DiscoveryRuntime(registry, cache_ttl_seconds=ttl, clock=clock)
    return runtime, clock


def test_runtime_caches_results_without_repeating_adapter_call():
    adapter = CountingAdapter()
    runtime, _ = setup_runtime(adapter)

    first = runtime.discover("counting")
    second = runtime.discover("counting")

    assert first == second
    assert adapter.calls == 1
    assert runtime.get_health("counting").status == "healthy"
    assert runtime.get_health("counting").cached is True


def test_runtime_refreshes_after_cache_ttl_expires():
    adapter = CountingAdapter()
    runtime, clock = setup_runtime(adapter, ttl=10)

    runtime.discover("counting")
    clock.advance(11)
    runtime.discover("counting")

    assert adapter.calls == 2


def test_runtime_enforces_manifest_per_minute_limit_even_on_forced_refresh():
    adapter = CountingAdapter(limit=1)
    runtime, _ = setup_runtime(adapter)

    runtime.discover("counting", force_refresh=True)
    with pytest.raises(AdapterRateLimitError):
        runtime.discover("counting", force_refresh=True)
    assert adapter.calls == 1


def test_runtime_releases_rate_limit_after_sixty_seconds():
    adapter = CountingAdapter(limit=1)
    runtime, clock = setup_runtime(adapter)

    runtime.discover("counting", force_refresh=True)
    clock.advance(60)
    runtime.discover("counting", force_refresh=True)

    assert adapter.calls == 2


def test_runtime_reports_failure_without_exposing_exception_message():
    adapter = CountingAdapter(fail=True)
    runtime, _ = setup_runtime(adapter)

    with pytest.raises(TimeoutError):
        runtime.discover("counting")

    health = runtime.get_health("counting")
    assert health.status == "degraded"
    assert health.last_error_type == "TimeoutError"
    assert health.consecutive_failures == 1


def test_runtime_resets_failure_count_after_recovery():
    adapter = CountingAdapter(fail=True)
    runtime, _ = setup_runtime(adapter)

    with pytest.raises(TimeoutError):
        runtime.discover("counting")
    adapter.fail = False
    runtime.discover("counting", force_refresh=True)

    health = runtime.get_health("counting")
    assert health.status == "healthy"
    assert health.consecutive_failures == 0
    assert health.last_error_type is None


def test_runtime_rejects_unknown_adapter_and_can_clear_cache():
    adapter = CountingAdapter()
    runtime, _ = setup_runtime(adapter)

    with pytest.raises(KeyError):
        runtime.discover("missing")
    runtime.discover("counting")
    runtime.clear_cache("counting")
    runtime.discover("counting")

    assert adapter.calls == 2
