"""AutoEarn AI core package."""

from .discovery import SourceCandidate
from .opportunities import Opportunity, normalize_url, score_opportunity
from .registry import SourceRegistry

__all__ = [
    "Opportunity",
    "SourceCandidate",
    "SourceRegistry",
    "normalize_url",
    "score_opportunity",
]
