"""AutoEarn AI core package."""

from .adapters import AdapterManifest, AdapterRegistry, DiscoveredLead
from .discovery import SourceCandidate
from .evaluator import OpportunityCandidate, evaluate_candidate
from .opportunities import Opportunity, normalize_url, score_opportunity
from .registry import SourceRegistry
from .rss import PublicRssAdapter

__all__ = [
    "AdapterManifest",
    "AdapterRegistry",
    "DiscoveredLead",
    "Opportunity",
    "OpportunityCandidate",
    "PublicRssAdapter",
    "SourceCandidate",
    "SourceRegistry",
    "evaluate_candidate",
    "normalize_url",
    "score_opportunity",
]
