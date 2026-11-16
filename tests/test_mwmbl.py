import json
from io import BytesIO
from unittest.mock import patch

import pytest

from autoearn.mwmbl import MwmblSearchProvider


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.payload[:size]


def test_mwmbl_parses_v2_results_and_sends_query_and_limit():
    payload = {
        "query": "reward games",
        "number_of_results": 1,
        "monthly_usage": None,
        "monthly_limit": None,
        "results": [{
            "title": "Reward games",
            "url": "https://example.org/rewards",
            "content": "Terms and eligibility details",
            "engine": "mwmbl",
            "score": 0.9,
        }],
    }
    with patch("autoearn.mwmbl._respect_anonymous_rate_limit"), patch(
        "autoearn.mwmbl.urlopen", return_value=FakeResponse(payload)
    ) as mocked:
        results = MwmblSearchProvider().search("reward games", limit=7)

    assert len(results) == 1
    assert results[0].title == "Reward games"
    assert results[0].snippet == "Terms and eligibility details"
    assert results[0].provider == "mwmbl"
    request = mocked.call_args.args[0]
    assert "q=reward+games" in request.full_url
    assert "limit=" not in request.full_url
    assert request.get_header("X-api-key") is None


def test_mwmbl_optional_api_key_is_sent_as_header():
    payload = {"results": []}
    with patch("autoearn.mwmbl.urlopen", return_value=FakeResponse(payload)) as mocked:
        assert MwmblSearchProvider(api_key=" test-key ").search("games") == []
    request = mocked.call_args.args[0]
    assert request.get_header("X-api-key") == "test-key"


@pytest.mark.parametrize("query,limit", [("", 5), ("games", 0), ("games", 51), ("games", True)])
def test_mwmbl_rejects_invalid_input(query, limit):
    with pytest.raises(ValueError):
        MwmblSearchProvider().search(query, limit)


def test_mwmbl_rejects_invalid_json_response():
    class InvalidResponse(FakeResponse):
        def __init__(self):
            self.payload = b"not-json"

    with patch("autoearn.mwmbl._respect_anonymous_rate_limit"), patch(
        "autoearn.mwmbl.urlopen", return_value=InvalidResponse()
    ):
        with pytest.raises(RuntimeError):
            MwmblSearchProvider().search("games")
