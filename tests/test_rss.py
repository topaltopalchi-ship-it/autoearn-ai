import pytest

from autoearn.rss import PublicRssAdapter


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


def test_discovered_item_must_stay_on_allowlisted_domain():
    payload = b'<rss><channel><item><title>Bad</title><link>https://evil.example/x</link></item></channel></rss>'
    with pytest.raises(ValueError, match="allowlisted"):
        adapter(fetcher=lambda url: payload).discover()


def test_feed_size_and_xml_are_validated():
    with pytest.raises(ValueError, match="1 MB"):
        adapter(fetcher=lambda url: b"x" * (1_000_001,)).discover()
    with pytest.raises(ValueError, match="XML"):
        adapter(fetcher=lambda url: b"<rss").discover()


def test_atom_feed_is_supported():
    payload = b'''<feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Design brief</title><link href="https://feed.example/jobs/1"/>
      <summary>Paid design work</summary></entry></feed>'''
    lead = adapter(fetcher=lambda url: payload).discover()[0]
    assert lead.title == "Design brief"
    assert lead.summary == "Paid design work"
