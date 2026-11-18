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


def test_lead_rejects_track_from_unrelated_parent_category():
    with pytest.raises(ValueError, match="track_key"):
        DiscoveredLead(
            title="Puzzle",
            url="https://example.com/puzzle",
            category="surveys_microtasks",
            source_name="Demo",
            observed_at="2026-11-17T10:00:00+00:00",
            track_key="puzzle_solving",
        )


def test_broad_category_lead_is_flagged_for_track_review():
    lead = DemoAdapter().discover()[0]
    source = source_candidate_from_lead(lead)
    assert source.track_key == ""
    assert source.track_review_status == "needs_review"


def test_unique_track_keywords_are_inferred():
    lead = DiscoveredLead(
        title="Solve this logic puzzle",
        url="https://example.com/puzzle",
        category="games_competitions",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
    )
    source = source_candidate_from_lead(lead)
    assert source.track_key == "puzzle_solving"
    assert source.track_review_status == "matched"


def test_ambiguous_track_keywords_remain_for_manual_review():
    lead = DiscoveredLead(
        title="Puzzle and IQ test challenge",
        url="https://example.com/mixed",
        category="games_competitions",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
    )
    source = source_candidate_from_lead(lead)
    assert source.track_key == ""
    assert source.track_review_status == "needs_review"


def test_explicit_valid_track_is_preserved_as_matched():
    lead = DiscoveredLead(
        title="Puzzle challenge",
        url="https://example.com/puzzle",
        category="games_competitions",
        source_name="Demo",
        observed_at="2026-11-17T10:00:00+00:00",
        track_key="puzzle_solving",
    )
    source = source_candidate_from_lead(lead)
    assert source.track_key == "puzzle_solving"
    assert source.track_review_status == "matched"


@pytest.mark.parametrize("url", [
    "http://example.com/task",
    "https://example.com:8443/task",
    "https://example.com/task#fragment",
])
def test_discovered_lead_rejects_insecure_or_noncanonical_urls(url):
    with pytest.raises(ValueError):
        DiscoveredLead(
            title="Unsafe lead",
            url=url,
            category="surveys_microtasks",
            source_name="Demo",
            observed_at="2026-11-17T10:00:00+00:00",
        )


@pytest.mark.parametrize("terms_url", [
    "http://example.com/terms",
    "https://example.com:9443/terms",
    "https://example.com/terms#section",
])
def test_discovered_lead_rejects_insecure_terms_urls(terms_url):
    with pytest.raises(ValueError):
        DiscoveredLead(
            title="Terms lead",
            url="https://example.com/task",
            category="surveys_microtasks",
            source_name="Demo",
            observed_at="2026-11-17T10:00:00+00:00",
            terms_url=terms_url,
        )


@pytest.mark.parametrize("categories", [
    (),
    ("unknown_category",),
    ("other", "other"),
    ["other"],
])
def test_manifest_rejects_invalid_or_duplicate_categories(categories):
    with pytest.raises(ValueError):
        AdapterManifest(
            adapter_id="bad-category",
            display_name="Bad category",
            categories=categories,
            allowed_domains=("example.com",),
        )


@pytest.mark.parametrize("actions", [
    ("SubmitEntry",),
    ("submit-entry",),
    ("submit_entry", "submit_entry"),
    ("../submit",),
])
def test_manifest_rejects_malformed_or_duplicate_actions(actions):
    with pytest.raises(ValueError):
        AdapterManifest(
            adapter_id="bad-action",
            display_name="Bad action",
            categories=("games_competitions",),
            execution_mode="official_api",
            allowed_domains=("example.com",),
            allowed_actions=actions,
            terms_permit_automation=True,
        )


def test_manifest_rejects_unknown_execution_mode():
    with pytest.raises(ValueError, match="execution_mode"):
        AdapterManifest(
            adapter_id="bad-mode",
            display_name="Bad mode",
            categories=("other",),
            execution_mode="browser_automation",
            allowed_domains=("example.com",),
        )


@pytest.mark.parametrize("kwargs", [
    {"adapter_id": None},
    {"adapter_id": "Bad ID"},
    {"display_name": ""},
    {"display_name": "x" * 121},
    {"categories": ("other", [])},
    {"allowed_domains": (123,)},
    {"allowed_actions": ("ok", [])},
    {"requests_per_minute": True},
    {"requests_per_minute": 1.5},
    {"terms_permit_automation": 1},
])
def test_manifest_rejects_malformed_field_types(kwargs):
    values = {
        "adapter_id": "field-check",
        "display_name": "Field check",
        "categories": ("other",),
        "allowed_domains": ("example.com",),
    }
    values.update(kwargs)
    with pytest.raises((ValueError, TypeError)):
        AdapterManifest(**values)


@pytest.mark.parametrize("execution_mode", [None, [], 7])
def test_manifest_rejects_non_string_execution_mode(execution_mode):
    with pytest.raises(ValueError, match="execution_mode"):
        AdapterManifest(
            adapter_id="bad-mode-type",
            display_name="Bad mode type",
            categories=("other",),
            execution_mode=execution_mode,
            allowed_domains=("example.com",),
        )


def test_adapter_rejects_embedded_url_credentials_even_on_allowed_host():
    with pytest.raises(ValueError, match="credentials"):
        DiscoveredLead(
            title="Credential URL",
            url="https://attacker:secret@example.com/task",
            category="surveys_microtasks",
            source_name="Demo",
            observed_at="2026-11-17T10:00:00+00:00",
        )


def test_registry_freezes_manifest_capabilities_at_registration():
    adapter = DemoAdapter()
    registry = AdapterRegistry()
    original = adapter.manifest
    registry.register(adapter)

    # A later dynamic/property mutation must not widen the registered host allowlist.
    adapter.manifest = AdapterManifest(
        adapter_id="demo",
        display_name="Mutated adapter",
        categories=("surveys_microtasks", "freelancing_services"),
        allowed_domains=("evil.example",),
    )
    assert registry.get_manifest("demo") == original
    assert registry.list_manifests() == [original]
    adapter.leads = [DiscoveredLead(
        title="Unexpected host", url="https://evil.example/task",
        category="surveys_microtasks", source_name="Demo",
        observed_at="2026-11-18T10:00:00+00:00",
    )]
    with pytest.raises(ValueError, match="allowlist"):
        registry.discover("demo")
