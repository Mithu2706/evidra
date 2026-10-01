"""Placeholders for future evidence sources. Intentionally not implemented in V1."""

from __future__ import annotations

from ...schemas.evidence import EvidenceUnit
from .base import SourceIngestor, SourceNotSupported


class GitHubRepositoryIngestor(SourceIngestor):
    """V2: clone a repository and emit file-level evidence (README, architecture, tests)."""

    source_type = "github"
    planned_version = "V2"

    def ingest(self, reference: str) -> list[EvidenceUnit]:
        raise SourceNotSupported("GitHub repository analysis is planned for V2 and is not available in V1.")


class WebsiteIngestor(SourceIngestor):
    """V3: inspect a demo URL (sandboxed, non-autonomous) and emit page-level evidence."""

    source_type = "website"
    planned_version = "V3"

    def ingest(self, reference: str) -> list[EvidenceUnit]:
        raise SourceNotSupported("Demo URL analysis is planned for V3 and is not available in V1.")


class DemoVideoIngestor(SourceIngestor):
    """V3: transcribe a demo video and emit timestamped evidence segments."""

    source_type = "video"
    planned_version = "V3"

    def ingest(self, reference: str) -> list[EvidenceUnit]:
        raise SourceNotSupported("Demo video analysis is planned for V3 and is not available in V1.")


REGISTRY: dict[str, type[SourceIngestor]] = {
    cls.source_type: cls for cls in (GitHubRepositoryIngestor, WebsiteIngestor, DemoVideoIngestor)
}
