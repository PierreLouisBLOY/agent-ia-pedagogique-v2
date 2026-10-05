"""Native BTS selection; the teaching year is a local progression only."""
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import object_data

BTS_CONTEXT_CONTRACT = "BTS-INSTITUTIONAL-CONTEXT-1.0"
FIELDS = {"contract_id", "program_ref", "program_version", "process_ref", "activity_ref",
          "competency_refs", "notion_refs", "depth", "local_year"}


def validate_bts_selection(value: object, *, level: str, discipline: str) -> dict[str, object]:
    data = object_data(value, FIELDS)
    if (data["contract_id"] != BTS_CONTEXT_CONTRACT or level not in {"BTS_CG_YEAR_1", "BTS_CG_YEAR_2"}
            or data["local_year"] != level or discipline != "Comptabilité et gestion"):
        raise ValueError("P0_BTS_INSTITUTIONAL_FRAME")
    for key in ("program_ref", "program_version", "process_ref", "activity_ref"):
        if not isinstance(data[key], str) or not 1 <= len(str(data[key])) <= 200:
            raise ValueError("P0_INSTITUTIONAL_ID")
    for key in ("competency_refs", "notion_refs"):
        values = data[key]
        if (not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 16 or
                not all(isinstance(v, str) and 0 < len(v) <= 200 for v in values) or len(set(values)) != len(values)):
            raise ValueError("P0_INSTITUTIONAL_SELECTION")
    if data["depth"] not in {"DISCOVERY", "APPLICATION", "ANALYSIS"}:
        raise ValueError("P0_INSTITUTIONAL_DEPTH")
    return data
