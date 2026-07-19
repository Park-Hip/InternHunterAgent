from abc import ABC, abstractmethod
from collections.abc import Iterator

from src.services.ingestion.models import RawPosting


class JobSource(ABC):
    """Provider-agnostic interface for a job data source.

    Each board implements this with a concrete source name and a fetch method
    that yields verbatim RawPosting records. Persistence and transform are
    handled by downstream sub-tickets (T0009.4/T0009.5).
    """

    source: str  # class-level constant; each adapter sets its own value
    pages_failed: int = 0  # count of pages given up on after retries; adapters increment in fetch()

    @abstractmethod
    def fetch(self) -> Iterator[RawPosting]:
        """Yield raw postings for this source. No persistence, no transform."""
