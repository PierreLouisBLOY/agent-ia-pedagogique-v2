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
from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
)

OWNER_ADMISSION_SHA256 = "534a0de28e740e18a460ef107add7efe083c0c099ecb76204f30ed5f5fb1a94c"
ADMITTED_DOCUMENTS = {
    "A01": "30b4721c959817d5735143c8ae1819c16e1e8f30822629f2b5594f96099e554f",
    "A02": "0958329b557aacc8db928ee4b6751da1f3b02e8aa507fe3f00b2efad8b09e5c8",
    "A03": "d3a8ffdba6b96080b0866bc2290406ea81c420dff56b042987c9604fdf022fd7",
    "A04B": "7d742bb45c32c38061f48a208bb2c0e983ec098f4551d4749186d672a286856e",
}


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
