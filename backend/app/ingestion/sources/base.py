"""Extension point for non-document evidence sources.

V1 ingests only PDF/PPTX documents. Later versions add further sources that
produce EvidenceUnits with their own `source_type` and `source_location`:

    V2  github   -> source_location.kind = "file_path"   (e.g. "src/router.py#L40-72")
    V3  website  -> source_location.kind = "url"
    V3  video    -> source_location.kind = "timestamp"   (e.g. "00:03:12")

The AI pipeline consumes EvidenceUnits generically, so adding a source should
not require changes to the reasoning stages or the Judge Brief UI beyond a
viewer for the new location kind.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from ...schemas.evidence import EvidenceUnit, SourceType


class SourceNotSupported(NotImplementedError):
    pass


class SourceIngestor(ABC):
    source_type: ClassVar[SourceType]
    planned_version: ClassVar[str] = "V1"
    enabled: ClassVar[bool] = False

    @abstractmethod
    def ingest(self, reference: str) -> list[EvidenceUnit]:
        """Fetch/inspect `reference` (repo URL, demo URL, video file) into evidence units."""
