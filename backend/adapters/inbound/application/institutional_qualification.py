from collections.abc import Mapping

from backend.modules.knowledge_reference.application.commands.admit_institutional_qualification import (
    AdmitInstitutionalQualification,
)


class InstitutionalQualificationInbound:
    def __init__(self, command: AdmitInstitutionalQualification) -> None:
        self.command = command

    def execute(self, data: Mapping[str, object]) -> dict[str, object]:
        return self.command.execute(data)
