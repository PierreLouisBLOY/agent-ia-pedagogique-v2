from enum import StrEnum


class ReviewDimension(StrEnum):
    ACCURACY = "REV-ACC"
    COVERAGE = "REV-COV"
    PEDAGOGY = "REV-PED"
    INSTRUCTION = "REV-INS"
    STRUCTURE = "REV-STR"
    SOURCES = "REV-SRC"
    CONSISTENCY = "REV-CON"
    FORMAT = "REV-FMT"
    RISK = "REV-RSK"


class FindingSeverity(StrEnum):
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    BLOCKING = "blocking"


class OverallAssessment(StrEnum):
    ACCEPTABLE = "acceptable"
    ACCEPTABLE_WITH_RESERVATIONS = "acceptable_with_reservations"
    CORRECTION_REQUIRED = "correction_required"
    UNUSABLE = "unusable"
    INCOMPLETE = "incomplete"
