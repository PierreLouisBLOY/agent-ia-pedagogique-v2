"""Local Windows media composition without provider, network, credentials or store."""
from backend.adapters.inbound.application.course_media import CourseMediaInbound
from backend.adapters.inbound.application.production_media import ProductionMediaInbound
from backend.adapters.outbound.export.contextual_media import WindowsLocalIllustrationRenderer
from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker
from backend.modules.pedagogical_design.application.commands.prepare_production_media import (
    PrepareProductionMediaCommand,
)


def build_course_media(*, profile: str = "diagram-v1") -> CourseMediaInbound:
    if profile == "diagram-v1":
        return CourseMediaInbound(MediaAssetWorker(WindowsLocalDiagramRenderer()))
    if profile == "contextual-v2":
        return CourseMediaInbound(MediaAssetWorker(WindowsLocalIllustrationRenderer()))
    raise ValueError("MEDIA_RENDERER_PROFILE")


def build_production_media(*, profile: str = "diagram-v1") -> ProductionMediaInbound:
    """The successor reuses the same configured worker and renderer profiles."""
    return ProductionMediaInbound(PrepareProductionMediaCommand(build_course_media(profile=profile).worker))
