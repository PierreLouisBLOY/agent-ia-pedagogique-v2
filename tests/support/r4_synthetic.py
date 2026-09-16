"""Fresh artificial R4 identities; no pilot, historical exports or external data."""
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import as_plain, object_data
from backend.modules.work_orchestration.contracts.dto.saved_production import (
    SAVED_CONTRACT,
    SavedProduction,
)
from tests.support import r3_synthetic

PROD = "prod:" + "4" * 32
CONV = "conv:" + "4" * 32


def record(index=1, *, imported=False, draft=False):
    version = "ver:" + f"{index:032x}"
    view = object_data(as_plain(r3_synthetic.production(conversation_id=CONV).data))
    view.update(production_ref=PROD, version_ref=version)
    bundle = r3_synthetic.bundle().mutable_copy()
    bundle.update(production_ref=PROD, version_ref=version)
    for kind in ("correction", "marking"):
        bundle[kind].update(production_ref=PROD, version_ref=version)
    return SavedProduction({"contract_id": SAVED_CONTRACT, "view": view,
        "bundle": None if draft else bundle, "reviews": [], "validations": [],
        "origin": "IMPORTED_DOCUMENTARY" if imported else "LOCAL_APPLICATION",
        "provenance": {"ARTIFICIAL_EXPORT": "a" * 64} if imported else {},
        "reservations": ["Réserve artificielle R4 : aucune certification pédagogique globale."]})
