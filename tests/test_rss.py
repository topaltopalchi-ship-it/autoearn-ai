import pytest

from autoearn.rss import PublicRssAdapter


@pytest.fixture(autouse=True)
def public_dns_for_reserved_test_domains(monkeypatch):
    # The tests use reserved .example hostnames; resolve them to a documentation
    # public address without making network/DNS access part of the test suite.
    monkeypatch.setattr(
        "autoearn.rss.socket.getaddrinfo",
        lambda host, port, type=None: [
            (2, 1, 6, "", ("93.184.216.34", port or 443))
        ],
    )


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Remote paid task</title><link>https://feed.example/tasks/42</link>
<description><![CDATA[<p>Review details &amp; eligibility.</p>]]></description></item>
</channel></rss>"""


def adapter(fetcher=None, **kwargs):
    return PublicRssAdapter(
        adapter_id="public-feed",
        display_name="Public opportunities feed",
        feed_url="https://feed.example/rss.xml",
        category="freelancing_services",
        allowed_domains=("feed.example",),
        fetcher=fetcher or (lambda url: RSS),
        **kwargs,
    )


def test_rss_feed_yields_normalized_provenance_records():
    lead = adapter().discover()[0]
    assert lead.title == "Remote paid task"
    assert lead.url == "https://feed.example/tasks/42"
    assert lead.category == "freelancing_services"
    assert "Public RSS feed:" in lead.evidence[0]
    assert "eligibility" in lead.summary


def test_feed_url_requires_https_and_allowlisted_domain():
    with pytest.raises(ValueError, match="HTTPS"):
        PublicRssAdapter(
            adapter_id="bad", display_name="Bad", feed_url="http://feed.example/rss",
            category="other", allowed_domains=("feed.example",),
        )
    with pytest.raises(ValueError, match="allowlisted"):
        PublicRssAdapter(
            adapter_id="bad", display_name="Bad", feed_url="https://elsewhere.example/rss",
            category="other", allowed_domains=("feed.example",),
        )


def test_discovered_item_outside_allowlist_is_ignored():
    payload = b'<rss><channel><item><title>Bad</title><link>https://evil.example/x</link></item></channel></rss>'
    assert adapter(fetcher=lambda url: payload).discover() == []


def test_feed_size_and_xml_are_validated():
    with pytest.raises(ValueError, match="1 MB"):
        adapter(fetcher=lambda url: b"x" * 1_000_001).discover()
    with pytest.raises(ValueError, match="XML"):
        adapter(fetcher=lambda url: b"<rss").discover()


def test_atom_feed_is_supported():
    payload = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Design brief</title><link href="https://feed.example/jobs/1"/>
      <summary>Paid design work</summary></entry></feed>'''
    lead = adapter(fetcher=lambda url: payload).discover()[0]
    assert lead.title == "Design brief"
    assert lead.summary == "Paid design work"


def test_feed_rejects_dtd_and_entity_declarations():
    payload = b'<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel></channel></rss>'
    with pytest.raises(ValueError, match="DTD/entities"):
        adapter(fetcher=lambda url: payload).discover()


def test_invalid_item_link_is_skipped_without_losing_valid_rss_items():
    payload = b'''<rss><channel>
      <item><title>Unsafe</title><link>https://evil.example/task</link></item>
      <item><title>Safe</title><link>https://feed.example/good</link></item>
    </channel></rss>'''
    leads = adapter(fetcher=lambda url: payload).discover()
    assert [lead.title for lead in leads] == ["Safe"]


def test_invalid_atom_link_is_skipped_without_losing_valid_entries():
    payload = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Unsafe</title><link href="https://evil.example/task"/></entry>
      <entry><title>Safe</title><link href="https://feed.example/good"/></entry>
    </feed>'''
    leads = adapter(fetcher=lambda url: payload).discover()
    assert [lead.title for lead in leads] == ["Safe"]


def test_feed_hostname_rejects_private_dns_answers(monkeypatch):
    monkeypatch.setattr(
        "autoearn.rss.socket.getaddrinfo",
        lambda host, port, type=None: [
            (2, 1, 6, "", ("127.0.0.1", port or 443))
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        adapter()


def test_feed_hostname_rejects_mixed_public_and_private_dns_answers(monkeypatch):
    monkeypatch.setattr(
        "autoearn.rss.socket.getaddrinfo",
        lambda host, port, type=None: [
            (2, 1, 6, "", ("93.184.216.34", port or 443)),
            (2, 1, 6, "", ("10.0.0.8", port or 443)),
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        adapter()


def test_feed_hostname_rejects_empty_dns_answer(monkeypatch):
    monkeypatch.setattr("autoearn.rss.socket.getaddrinfo", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="did not resolve"):
        adapter()


def test_feed_rejects_private_ip_literal():
    with pytest.raises(ValueError, match="non-public"):
        PublicRssAdapter(
            adapter_id="private-ip", display_name="Private IP",
            feed_url="https://127.0.0.1/rss",
            category="other", allowed_domains=("127.0.0.1",),
        )


def test_feed_fetch_uses_pinned_public_ip_and_hostname_tls(monkeypatch):
    from autoearn.rss import _PinnedHTTPSConnection

    calls = {}
    class FakeTlsContext:
        def wrap_socket(self, raw_socket, server_hostname):
            calls["server_hostname"] = server_hostname
            return "tls-socket"

    monkeypatch.setattr(
        "autoearn.rss.socket.create_connection",
        lambda address, timeout, source_address: calls.update(
            address=address, timeout=timeout
        ) or object(),
    )
    monkeypatch.setattr(
        _PinnedHTTPSConnection, "_context", FakeTlsContext(), raising=False
    )
    connection = _PinnedHTTPSConnection(
        "feed.example", "93.184.216.34", port=443, timeout=8
    )
    connection._context = FakeTlsContext()
    connection.connect()
    assert calls["address"] == ("93.184.216.34", 443)
    assert calls["server_hostname"] == "feed.example"
    assert connection.sock == "tls-socket"


def test_feed_fetch_does_not_follow_http_redirects(monkeypatch):
    from autoearn.rss import PublicRssAdapter

    calls = {}
    class FakeResponse:
        status = 302
        def read(self, limit):
            return b"redirect"

    class FakeConnection:
        def __init__(self, host, pinned_ip, **kwargs):
            calls["host"] = host
            calls["pinned_ip"] = pinned_ip
            calls["kwargs"] = kwargs
        def request(self, method, path, headers):
            calls["request"] = (method, path, headers)
        def getresponse(self):
            return FakeResponse()
        def close(self):
            calls["closed"] = True

    monkeypatch.setattr("autoearn.rss._PinnedHTTPSConnection", FakeConnection)
    feed = PublicRssAdapter(
        adapter_id="redirect-test", display_name="Redirect test",
        feed_url="https://feed.example/rss.xml?kind=jobs",
        category="other", allowed_domains=("feed.example",),
    )
    with pytest.raises(ValueError, match="HTTP 302"):
        feed._fetch(feed.feed_url)
    assert calls["host"] == "feed.example"
    assert calls["pinned_ip"] == "93.184.216.34"
    assert calls["request"][0:2] == ("GET", "/rss.xml?kind=jobs")
    assert calls["request"][2]["Host"] == "feed.example"
    assert calls["closed"] is True


def test_feed_fetch_enforces_response_size_limit(monkeypatch):
    from autoearn.rss import MAX_FEED_BYTES, PublicRssAdapter

    class FakeResponse:
        status = 200
        def read(self, limit):
            assert limit == MAX_FEED_BYTES + 1
            return b"x" * limit

    class FakeConnection:
        def __init__(self, *args, **kwargs):
            pass
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return FakeResponse()
        def close(self):
            pass

    monkeypatch.setattr("autoearn.rss._PinnedHTTPSConnection", FakeConnection)
    feed = PublicRssAdapter(
        adapter_id="size-test", display_name="Size test",
        feed_url="https://feed.example/rss.xml",
        category="other", allowed_domains=("feed.example",),
    )
    with pytest.raises(ValueError, match="1 MB"):
        feed._fetch(feed.feed_url)
