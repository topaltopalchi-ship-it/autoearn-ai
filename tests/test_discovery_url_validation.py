import pytest

from autoearn.discovery import SourceCandidate


def test_accepts_public_https_source_and_terms_urls():
    candidate = SourceCandidate(
        "Reward platform",
        "https://rewards.example.org/offers",
        terms_url="https://rewards.example.org/terms",
    )
    assert candidate.canonical_url == "https://rewards.example.org/offers"
    assert candidate.to_record()["terms_url"] == "https://rewards.example.org/terms"


@pytest.mark.parametrize(
    "url",
    [
        "http://rewards.example.org",
        "https://localhost/rewards",
        "https://service.local/rewards",
        "https://service.internal/rewards",
        "https://service.test/rewards",
        "https://service.invalid/rewards",
        "https://service.example/rewards",
        "https://127.0.0.1/rewards",
        "https://10.0.0.8/rewards",
        "https://[::1]/rewards",
        "https://user:password@rewards.example.org/rewards",
        "https://rewards.example.org:8443/rewards",
    ],
)
def test_rejects_non_public_or_unsafe_source_urls(url):
    with pytest.raises(ValueError):
        SourceCandidate("Unsafe source", url)


def test_rejects_unsafe_terms_url_even_when_source_url_is_valid():
    with pytest.raises(ValueError):
        SourceCandidate(
            "Reward platform",
            "https://rewards.example.org/offers",
            terms_url="https://127.0.0.1/private-terms",
        )
