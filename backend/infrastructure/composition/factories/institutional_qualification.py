"""Owner-admitted public corpus, fresh authenticated copy only; no agent SQL."""

from collections.abc import Mapping
from pathlib import Path

from backend.adapters.inbound.application.institutional_qualification import (
    InstitutionalQualificationInbound,
)
from backend.adapters.outbound.persistence.sqlite import connect_sqlite
from backend.adapters.outbound.resource_library.institutional_qualification_sqlite import (
    SQLiteInstitutionalQualificationAdapter,
)
from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget
from backend.infrastructure.filesystem import (
    assert_local_data_root,
    atomic_publish_fresh,
    capture_secure_path,
    ensure_private_directory,
    hash_file_nofollow,
    private_temporary_file,
    read_file_nofollow,
)
from backend.modules.knowledge_reference.application.commands.admit_institutional_qualification import (
    AdmitInstitutionalQualification,
)
from backend.modules.knowledge_reference.contracts.dto.admitted_institutional_sources import (
    ADMITTED_DOCUMENTS,
    OWNER_ADMISSION_SHA256,
)
from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)


def qualify_isolated_catalog(
    *,
    original: Read15RuntimeTarget,
    destination: Path,
    data_root: Path,
    owner_decision_path: Path,
    public_files: Mapping[str, Path],
    qualification: Mapping[str, object],
) -> tuple[Read15RuntimeTarget, dict[str, object]]:
    original.validate()
    qualified = InstitutionalQualification(qualification)
    if qualified.data["owner_decision_sha256"] != OWNER_ADMISSION_SHA256:
        raise ValueError("INSTITUTIONAL_OWNER_DECISION_CHANGED")
    if (
        hash_file_nofollow(owner_decision_path, allowed_root=owner_decision_path.parent)
        != OWNER_ADMISSION_SHA256
    ):
        raise ValueError("INSTITUTIONAL_OWNER_DECISION_CHANGED")
    if set(public_files) != set(ADMITTED_DOCUMENTS):
        raise ValueError("INSTITUTIONAL_PUBLIC_CORPUS_REQUIRED")
    for key, file in public_files.items():
        if hash_file_nofollow(file, allowed_root=file.parent) != ADMITTED_DOCUMENTS[key]:
            raise ValueError("INSTITUTIONAL_PUBLIC_FILE_CHANGED")
    root_path = assert_local_data_root(data_root)
    repository = Path(__file__).resolve().parents[4]
    if root_path == repository or root_path.is_relative_to(repository):
        raise ValueError("RUNTIME_OUTSIDE_REPOSITORY_REQUIRED")
    root = Read15RuntimeTarget(destination, root_path, original.expected_sha256)
    # Validate the root and prohibit redirects before creating any candidate.
    ensure_private_directory(root.data_root, allowed_root=root.data_root)
    if capture_secure_path(destination, allowed_root=data_root).exists:
        raise ValueError("INSTITUTIONAL_FRESH_CANDIDATE_REQUIRED")
    if destination.resolve() == original.runtime_path.resolve():
        raise ValueError("INSTITUTIONAL_ORIGINAL_MUTATION_FORBIDDEN")
    payload = read_file_nofollow(
        original.runtime_path, allowed_root=original.data_root, maximum_bytes=512 * 1024 * 1024
    )
    original.validate()
    temporary = private_temporary_file(
        data_root, allowed_root=data_root, prefix="institutional-", suffix=".sqlite"
    )
    temporary.write_bytes(payload)
    copied = Read15RuntimeTarget(temporary, data_root, original.expected_sha256)
    copied.validate()
    connection = connect_sqlite(temporary, allowed_root=data_root)
    try:
        inbound = InstitutionalQualificationInbound(
            AdmitInstitutionalQualification(
                SQLiteInstitutionalQualificationAdapter(connection),
                owner_decision_sha256=OWNER_ADMISSION_SHA256,
                admitted_document_hashes=ADMITTED_DOCUMENTS,
            )
        )
        receipt = inbound.execute(qualified.as_dict())
    finally:
        connection.close()
    original.validate()
    atomic_publish_fresh(temporary, destination, allowed_root=data_root)
    target = Read15RuntimeTarget(
        destination, data_root, hash_file_nofollow(destination, allowed_root=data_root)
    )
    target.validate()
    return target, {
        **receipt,
        "source_sha256": original.expected_sha256,
        "candidate_sha256": target.expected_sha256,
        "original_modified": False,
    }
