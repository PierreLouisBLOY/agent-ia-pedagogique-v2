from enum import StrEnum


class ContractFamily(StrEnum):
    C01 = "C-01"
    C02 = "C-02"
    C03 = "C-03"
    C04 = "C-04"
    C05 = "C-05"
    C06 = "C-06"
    C07 = "C-07"
    C08 = "C-08"
    C09 = "C-09"
    C10 = "C-10"
    C11 = "C-11"
    C12 = "C-12"
    C13 = "C-13"
    C14 = "C-14"
    C15 = "C-15"
    C16 = "C-16"
    C17 = "C-17"
    C18 = "C-18"
    C19 = "C-19"


class SupplementalContractKind(StrEnum):
    CORRECTION_RESULT = "CorrectionResult"


type VersionedContractKey = ContractFamily | SupplementalContractKind


class MetadataMode(StrEnum):
    DIRECT_META = "DIRECT_META"
    COMPOSED_META = "COMPOSED_META"
    NESTED_VALUE = "NESTED_VALUE"


class ContractChangeKind(StrEnum):
    ADDITIVE = "additive"
    REMOVAL = "removal"
    RENAME = "rename"
    SEMANTIC_CHANGE = "semantic_change"


class VersionBump(StrEnum):
    MINOR = "minor"
    MAJOR = "major"
