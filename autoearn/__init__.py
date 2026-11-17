"""AutoEarn AI core package."""

from .adapters import AdapterManifest, AdapterRegistry, DiscoveredLead
from .discovery import SourceCandidate
from .evaluator import OpportunityCandidate, evaluate_candidate
from .opportunities import Opportunity, normalize_url, score_opportunity
from .registry import SourceRegistry

__all__ = [
    "AdapterManifest",
    "AdapterRegistry",
    "DiscoveredLead",
    "Opportunity",
    "OpportunityCandidate",
    "SourceCandidate",
    "SourceRegistry",
    "evaluate_candidate",
    "normalize_url",
    "score_opportunity",
]
