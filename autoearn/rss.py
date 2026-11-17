"""Read-only RSS/Atom discovery adapter for explicitly configured public feeds.

The feed URL and allowed hostnames are trusted configuration, never values
taken from a discovered item. Redirects are disabled; only HTTPS and exact
host allowlists are accepted. No page scraping or platform actions occur.
"""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
from html.parser import HTMLParser
from urllib.parse import urlsplit
import ssl
import ipaddress
import socket
import xml.etree.ElementTree as ET

from .adapters import AdapterManifest, DiscoveredLead
from .opportunities import normalize_url


MAX_FEED_BYTES = 1_000_000


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)


def _plain_text(value: str, limit: int = 600) -> str:
    parser = _TextOnly()
    parser.feed(value or "")
    return " ".join(parser.parts)[:limit]


def _resolve_public_addresses(host: str, port: int) -> tuple[str, ...]:
    """Resolve once and reject every non-public answer before any connection."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as dns_error:
            raise ValueError("feed hostname could not be resolved") from dns_error
        if not answers:
            raise ValueError("feed hostname did not resolve to a public address")
        addresses = tuple(dict.fromkeys(ipaddress.ip_address(item[4][0]).compressed for item in answers))
    else:
        addresses = (literal.compressed,)
    if any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError("feed host resolves to a non-public address")
    return addresses


def _validate_public_https_target(
    url: str, allowed_domains: tuple[str, ...]
) -> tuple[str, str]:
    canonical = normalize_url(url)
    parsed = urlsplit(canonical)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https":
        raise ValueError("RSS feed URLs must use HTTPS")
    if not allowed_domains or host not in {d.casefold() for d in allowed_domains}:
        raise ValueError("feed host must be explicitly allowlisted")
    addresses = _resolve_public_addresses(host, parsed.port or 443)
    return canonical, addresses[0]


def _validate_public_https(url: str, allowed_domains: tuple[str, ...]) -> str:
    return _validate_public_https_target(url, allowed_domains)[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """TLS connection pinned to a validated IP while preserving hostname SNI."""

    def __init__(self, host: str, pinned_ip: str, **kwargs):
        super().__init__(host, **kwargs)
        self._pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout, self.source_address
        )
        try:
            self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
        except Exception:
            raw_socket.close()
            raise


class PublicRssAdapter:
    """Fetch and parse a configured RSS/Atom feed as discovery-only metadata."""

    def __init__(
        self,
        *,
        adapter_id: str,
        display_name: str,
        feed_url: str,
        category: str,
        allowed_domains: tuple[str, ...],
        fetcher=None,
        timeout_seconds: int = 8,
        max_items: int = 30,
    ) -> None:
        if not 1 <= timeout_seconds <= 20:
            raise ValueError("timeout_seconds must be between 1 and 20")
        if not 1 <= max_items <= 100:
            raise ValueError("max_items must be between 1 and 100")
        self.feed_url, self._pinned_ip = _validate_public_https_target(feed_url, allowed_domains)
        self.category = category
        self.allowed_domains = allowed_domains
        self.fetcher = fetcher or self._fetch
        self.timeout_seconds = timeout_seconds
        self.max_items = max_items
        self._manifest = AdapterManifest(
            adapter_id=adapter_id,
            display_name=display_name,
            categories=(category,),
            execution_mode="manual",
            allowed_domains=allowed_domains,
            requests_per_minute=6,
            requires_user_approval=True,
        )

    @property
    def manifest(self) -> AdapterManifest:
        return self._manifest

    def _fetch(self, url: str) -> bytes:
        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection = _PinnedHTTPSConnection(
            parsed.hostname or "", self._pinned_ip,
            port=parsed.port or 443, timeout=self.timeout_seconds,
            context=ssl.create_default_context(),
        )
        try:
            connection.request(
                "GET", path,
                headers={
                    "Host": parsed.netloc,
                    "User-Agent": "AutoEarnAI-Discovery/1.0",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                # Redirects are intentionally not followed.
                raise ValueError(f"feed request rejected with HTTP {response.status}")
            data = response.read(MAX_FEED_BYTES + 1)
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise ValueError("feed request failed") from exc
        finally:
            connection.close()
        if len(data) > MAX_FEED_BYTES:
            raise ValueError("feed exceeds the 1 MB size limit")
        return data

    def discover(self) -> list[DiscoveredLead]:
        payload = self.fetcher(self.feed_url)
        if not isinstance(payload, bytes) or len(payload) > MAX_FEED_BYTES:
            raise ValueError("feed fetcher must return at most 1 MB of bytes")
        upper_payload = payload.upper()
        if b"<!DOCTYPE" in upper_payload or b"<!ENTITY" in upper_payload:
            raise ValueError("feed XML declarations with DTD/entities are not accepted")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ValueError("feed XML is invalid") from exc

        observed = datetime.now(timezone.utc).isoformat()
        results: list[DiscoveredLead] = []
        # RSS 2.0
        for item in root.findall("./channel/item"):
            title = _plain_text(item.findtext("title", ""))
            link = (item.findtext("link", "") or "").strip()
            description = _plain_text(item.findtext("description", ""))
            if not title or not link:
                continue
            try:
                canonical_link = _validate_public_https(link, self.allowed_domains)
            except ValueError:
                # Reject this item without discarding otherwise valid feed entries.
                continue
            results.append(DiscoveredLead(
                title=title,
                url=canonical_link,
                category=self.category,
                source_name=self.manifest.display_name,
                observed_at=observed,
                summary=description,
                evidence=(f"Public RSS feed: {self.feed_url}",),
            ))
            if len(results) >= self.max_items:
                break

        # Atom
        if not results:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            for entry in root.findall(".//a:entry", ns):
                title = _plain_text(entry.findtext("a:title", default="", namespaces=ns))
                link_el = entry.find("a:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = _plain_text(entry.findtext("a:summary", default="", namespaces=ns))
                if not title or not link:
                    continue
                try:
                    canonical_link = _validate_public_https(link, self.allowed_domains)
                except ValueError:
                    # Reject this item without discarding otherwise valid feed entries.
                    continue
                results.append(DiscoveredLead(
                    title=title,
                    url=canonical_link,
                    category=self.category,
                    source_name=self.manifest.display_name,
                    observed_at=observed,
                    summary=summary,
                    evidence=(f"Public Atom feed: {self.feed_url}",),
                ))
                if len(results) >= self.max_items:
                    break
        return results
