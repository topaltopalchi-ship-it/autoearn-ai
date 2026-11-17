import pytest

from autoearn.adapters import (
    AdapterManifest,
    AdapterRegistry,
    DiscoveredLead,
    source_candidate_from_lead,
)


class DemoAdapter:
    def __init__(self, manifest=None, leads=None):
        self.manifest = manifest or AdapterManifest(
            adapter_id="demo",
            display_name="Demo public feed",
            categories=("surveys_microtasks", "freelancing_services"),
            allowed_domains=("example.com",),
        )
        self.leads = leads if leads is not None else [
            DiscoveredLead(
                title="Research task",
                url="https://example.com/tasks/1",
                category="surveys_microtasks",
                source_name="Demo public feed",
                observed_at="2026-11-17T10:00:00+00:00",
                summary="Reward details require review",
                evidence=("Public listing metadata",),
            )
        ]

    def discover(self):
        return self.leads


def test_registry_discovers_only_registered_adapter_and_returns_leads():
    registry = AdapterRegistry()
    registry.register(DemoAdapter())
    leads = registry.discover("demo")
    assert len(leads) == 1
    assert leads[0].title == "Research task"


def test_manifest_requires_an_explicit_exact_domain_allowlist():
    with pytest.raises(ValueError, match="exact allowed domain"):
        AdapterManifest(
            adapter_id="unrestricted",
            display_name="Unrestricted adapter",
            categories=("other",),
        )


@pytest.mark.parametrize("domain", ["*.example.com", "Example.com", "example", "bad..example.com", "example.com/path", "example.com:443"])
def test_manifest_rejects_non_exact_or_malformed_domains(domain):
    with pytest.raises(ValueError, match="exact public hostnames"):
        AdapterManifest(
            adapter_id="invalid-domain",
            display_name="Invalid domain",
            categories=("other",),
            allowed_domains=(domain,),
        )


def test_allowlist_does_not_implicitly_include_subdomains():
    lead = DiscoveredLead(
        title="Subdomain task",
        url="https://sub.example.com/task",
        category="surveys_microtasks",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
    )
    registry = AdapterRegistry()
    registry.register(DemoAdapter(leads=[lead]))
    with pytest.raises(ValueError, match="allowlist"):
        registry.discover("demo")


def test_unknown_adapter_cannot_run():
    with pytest.raises(KeyError):
        AdapterRegistry().discover("not-installed")


def test_duplicate_adapter_id_is_rejected():
    registry = AdapterRegistry()
    registry.register(DemoAdapter())
    with pytest.raises(ValueError):
        registry.register(DemoAdapter())


def test_adapter_cannot_return_category_outside_manifest():
    lead = DiscoveredLead(
        title="Competition",
        url="https://example.com/comp",
        category="games_competitions",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
    )
    registry = AdapterRegistry()
    registry.register(DemoAdapter(leads=[lead]))
    with pytest.raises(ValueError, match="categories"):
        registry.discover("demo")


def test_adapter_cannot_escape_domain_allowlist():
    lead = DiscoveredLead(
        title="External task",
        url="https://evil.example/task",
        category="surveys_microtasks",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
    )
    registry = AdapterRegistry()
    registry.register(DemoAdapter(leads=[lead]))
    with pytest.raises(ValueError, match="allowlist"):
        registry.discover("demo")


def test_source_candidate_from_lead_always_requires_review():
    lead = DemoAdapter().discover()[0]
    source = source_candidate_from_lead(lead)
    assert source.status == "pending"
    assert source.category == "surveys_microtasks"


def test_platform_actions_require_terms_permission_and_user_approval():
    with pytest.raises(ValueError, match="terms permission"):
        AdapterManifest(
            adapter_id="unsafe",
            display_name="Unsafe",
            categories=("games_competitions",),
            execution_mode="official_api",
            allowed_domains=("example.com",),
            allowed_actions=("submit_entry",),
            terms_permit_automation=False,
        )
    with pytest.raises(ValueError, match="user approval"):
        AdapterManifest(
            adapter_id="unsafe2",
            display_name="Unsafe",
            categories=("games_competitions",),
            execution_mode="official_api",
            allowed_domains=("example.com",),
            allowed_actions=("submit_entry",),
            terms_permit_automation=True,
            requires_user_approval=False,
        )
