"""Local Windows media composition without provider, network, credentials or store."""
from backend.adapters.inbound.application.course_media import CourseMediaInbound
from backend.adapters.outbound.export.local_media import WindowsLocalDiagramRenderer
from backend.modules.materialization_export.application.services.media_asset import MediaAssetWorker


def build_course_media() -> CourseMediaInbound:
    return CourseMediaInbound(MediaAssetWorker(WindowsLocalDiagramRenderer()))
