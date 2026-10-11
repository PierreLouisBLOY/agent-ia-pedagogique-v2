from collections.abc import Mapping

from backend.modules.knowledge_reference.contracts.dto.institutional_qualification import (
    InstitutionalQualification,
    sha,
)
from backend.modules.knowledge_reference.ports.outbound.institutional_qualification import (
    InstitutionalQualificationPort,
)
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import items, object_data


class AdmitInstitutionalQualification:
    def __init__(
        self,
        port: InstitutionalQualificationPort,
        *,
        owner_decision_sha256: str,
        admitted_document_hashes: Mapping[str, str],
    ) -> None:
        self.port = port
        self.owner_decision_sha256 = sha(owner_decision_sha256)
        self.admitted = {k: sha(v) for k, v in admitted_document_hashes.items()}

    def execute(self, data: Mapping[str, object]) -> dict[str, object]:
        qualified = InstitutionalQualification(data)
        if qualified.data["owner_decision_sha256"] != self.owner_decision_sha256:
            raise ValueError("INSTITUTIONAL_OWNER_DECISION_CHANGED")
        for doc in items(qualified.data["documents"]):
            if self.admitted.get(str(doc["candidate_id"])) != doc["sha256"]:
                raise ValueError("INSTITUTIONAL_DOCUMENT_NOT_ADMITTED")
        self.port.publish_qualification(qualified)
        return object_data(
            {
                "contract_id": "INSTITUTIONAL-ADMISSION-RECEIPT-1.0",
                "qualification_sha256": qualified.sha256,
                "notion_count": 628,
                "original_modified": False,
                "provider_calls": 0,
                "status": "PERSISTED_QUALIFICATION_NOT_PEDAGOGICAL_ACCEPTANCE",
            }
        )
