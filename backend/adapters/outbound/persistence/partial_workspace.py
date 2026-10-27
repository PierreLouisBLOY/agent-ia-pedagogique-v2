"""Pinned recovered artifacts only; no access to command, budget or receipt stores."""
import hashlib
import json
import os
from pathlib import Path

from backend.infrastructure.filesystem import (
    LocalFileSecurityCode,
    LocalFileSecurityError,
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import (
    encoded,
    object_data,
)
from backend.modules.work_orchestration.contracts.dto.p0_captured_partial import (
    CapturedPartial,
    CapturedPartialRequest,
)
from backend.modules.work_orchestration.contracts.dto.p1_campaign_inspection import (
    P1CampaignInspectionView,
)

_ROOT = Path(__file__).resolve().parents[4]
_FIELDS = {"schema", "request", "text_file", "metadata_file", "metadata_sha256", "read_record_file", "read_record_sha256"}


def closed_json(raw: bytes) -> dict[str, object]:
    def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
        if len(dict(entries)) != len(entries):
            raise ValueError("PARTIAL_DUPLICATE_FIELD")
        return dict(entries)
    return object_data(json.loads(raw, object_pairs_hook=pairs))


class LocalPartialWorkspace:
    def __init__(self, manifest: Path, manifest_sha256: str, root: Path) -> None:
        self.artifact_root = assert_local_data_root(manifest.parent)
        self.root = assert_local_data_root(root)
        self.manifest = capture_secure_path(manifest, allowed_root=self.artifact_root).path
        if (self.root == _ROOT or _ROOT in self.root.parents
                or self.manifest == _ROOT or _ROOT in self.manifest.parents):
            raise ValueError("PARTIAL_OUTSIDE_SOURCE_REQUIRED")
        self.manifest_sha256 = manifest_sha256
        self.saved_path = self.root / "captured-partial-native-tables-v1.json"
        self.read()

    def _pinned(self, path: Path, pin: object, maximum: int) -> bytes:
        raw = read_file_nofollow(path, allowed_root=self.artifact_root, maximum_bytes=maximum)
        if type(pin) is not str or hashlib.sha256(raw).hexdigest() != pin:
            raise ValueError("PARTIAL_IDENTITY_CHANGED")
        return raw

    def _path(self, value: object) -> Path:
        if type(value) is not str or "\\" in value:
            raise ValueError("PARTIAL_PATH_REJECTED")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("PARTIAL_PATH_REJECTED")
        return self.artifact_root / relative

    def read(self) -> CapturedPartial:
        manifest = self._manifest()
        if manifest["schema"] != "V2-CAPTURED-PARTIAL-LOCAL-1.0":
            raise ValueError("PARTIAL_MANIFEST_REJECTED")
        values = object_data(manifest["request"], {"command_id", "profile_sha256", "request_sha256",
            "result_sha256", "text_sha256", "text_bytes"})
        request = CapturedPartialRequest(**values)  # type: ignore[arg-type]
        raw = self._pinned(self._path(manifest["text_file"]), request.text_sha256, 65536)
        metadata = closed_json(self._pinned(self._path(manifest["metadata_file"]), manifest["metadata_sha256"], 65536))
        record = closed_json(self._pinned(self._path(manifest["read_record_file"]), manifest["read_record_sha256"], 65536))
        if (metadata["schema"] != "P1-PILOT-COMMAND-METADATA-1.1"
                or record.get("state") != "PARTIAL_CAPTURE_RECOVERED_UNVALIDATED"
                or any(record.get(key) != getattr(request, key) for key in
                    ("command_id", "result_sha256", "text_sha256", "text_bytes"))
                or record.get("inspection_profile_sha256") != request.profile_sha256):
            raise ValueError("PARTIAL_PROVENANCE_REJECTED")
        view = P1CampaignInspectionView.from_mapping(dict(metadata, schema="P0-PILOT-COMMAND-INSPECTION-1.1"))
        capture = CapturedPartial(request, raw.decode("utf-8"), view)
        # Recheck all pinned artifacts before returning; no business LOCK is acquired.
        self._pinned(self.manifest, self.manifest_sha256, 8192)
        self._pinned(self._path(manifest["metadata_file"]), manifest["metadata_sha256"], 65536)
        self._pinned(self._path(manifest["read_record_file"]), manifest["read_record_sha256"], 65536)
        self._pinned(self._path(manifest["text_file"]), request.text_sha256, 65536)
        return capture

    def _manifest(self) -> dict[str, object]:
        manifest = closed_json(self._pinned(self.manifest, self.manifest_sha256, 8192))
        if not _FIELDS <= set(manifest) or set(manifest) - _FIELDS - {"local_revision", "format_reference"}:
            raise ValueError("PARTIAL_MANIFEST_REJECTED")
        return manifest

    def read_format_admission(self) -> dict[str, object] | None:
        manifest = self._manifest()
        if "format_reference" not in manifest:
            return None
        admission = object_data(manifest["format_reference"], {"file", "sha256"})
        return closed_json(self._pinned(self._path(admission["file"]), admission["sha256"], 16384))

    def read_revision(self) -> dict[str, object] | None:
        manifest = self._manifest()
        if "local_revision" not in manifest:
            return None
        revision = object_data(manifest["local_revision"], {"file", "sha256"})
        return closed_json(self._pinned(self._path(revision["file"]), revision["sha256"], 65536))

    def _state(self, projection_sha256: str) -> bytes:
        return encoded({"schema": "V2-CAPTURED-PARTIAL-SAVED-1.0", "status": "PARTIAL_UNVALIDATED",
            "manifest_sha256": self.manifest_sha256, "projection": "native-tables-v1",
            "projection_sha256": projection_sha256})

    def is_saved(self, projection_sha256: str) -> bool:
        if not capture_secure_path(self.saved_path, allowed_root=self.root).exists:
            return False
        if read_file_nofollow(self.saved_path, allowed_root=self.root, maximum_bytes=2048) != self._state(projection_sha256):
            raise ValueError("PARTIAL_SAVED_IDENTITY_CHANGED")
        return True

    def save(self, capture: CapturedPartial, projection_sha256: str) -> None:
        self.read_revision()
        if self.read() != capture:
            raise ValueError("PARTIAL_IDENTITY_CHANGED")
        if self.is_saved(projection_sha256):
            return
        temporary = private_temporary_file(self.root, allowed_root=self.root, prefix="partial-", suffix=".pending")
        with temporary.open("wb") as stream:
            stream.write(self._state(projection_sha256))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            atomic_publish_fresh(temporary, self.saved_path, allowed_root=self.root)
        except LocalFileSecurityError as error:
            if error.code != LocalFileSecurityCode.DESTINATION_EXISTS or not self.is_saved(projection_sha256):
                raise
        if not self.is_saved(projection_sha256):
            raise ValueError("PARTIAL_SAVE_NOT_CONFIRMED")
