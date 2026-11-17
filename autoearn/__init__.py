"""AutoEarn AI core package."""

from .adapters import AdapterManifest, AdapterRegistry, DiscoveredLead
from .discovery import SourceCandidate
from .evaluator import OpportunityCandidate, evaluate_candidate
from .opportunities import Opportunity, normalize_url, score_opportunity
from .registry import SourceRegistry
from .rss import PublicRssAdapter
from .supervision import AuditEvent, SupervisedAction, SupervisionError, SupervisionQueue

__all__ = [
    "AdapterManifest",
    "AdapterRegistry",
    "AuditEvent",
    "DiscoveredLead",
    "Opportunity",
    "OpportunityCandidate",
    "PublicRssAdapter",
    "SourceCandidate",
    "SourceRegistry",
    "SupervisedAction",
    "SupervisionError",
    "SupervisionQueue",
    "evaluate_candidate",
    "normalize_url",
    "score_opportunity",
]
