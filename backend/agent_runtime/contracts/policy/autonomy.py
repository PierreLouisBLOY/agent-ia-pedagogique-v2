from enum import StrEnum


class AutonomyLevel(StrEnum):
    AUT_L0 = "AUT-L0"
    AUT_L1 = "AUT-L1"
    AUT_L2 = "AUT-L2"
    AUT_L3 = "AUT-L3"
    AUT_L4 = "AUT-L4"
    AUT_L5 = "AUT-L5"


class RuntimeMode(StrEnum):
    MODE_DIRECT = "MODE-DIRECT"
    MODE_ASSISTED = "MODE-ASSISTED"
    MODE_ORCHESTRATED = "MODE-ORCHESTRATED"
    MODE_HIGH_ASSURANCE = "MODE-HIGH_ASSURANCE"
