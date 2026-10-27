"""Same normal CLI/factories as 323C, with a deliberately compound synthetic row."""

from backend.modules.pedagogical_context.contracts.dto.exercise_context import LOCAL_FOCUS_AUTHORITY
from backend.modules.pedagogical_design.contracts.dto.assessment_bundle import fingerprint
from tests.focus_323d_fixture import LOCAL_LABEL
from tests.normal_on_323c_fixture import install as install_structured


def install(monkeypatch):
    f = install_structured(monkeypatch)
    old_catalog, old_context = f.Catalog, f.context

    class Catalog(old_catalog):
        def __init__(self):
            super().__init__()
            q = next(
                q
                for q in self.data["official_framework_element"]
                if q["id"] == "question:SGN_PREMIERE"
            )
            q.update(
                official_label="1.1 Comment définir les différents types d'organisation ? "
                + LOCAL_LABEL,
                official_text="SYNTHETIC_FOCUS_SOURCE_NOT_A_REAL_ADMISSION",
                position=1,
            )

    def context():
        c = old_context()
        q = next(
            q
            for q in Catalog().data["official_framework_element"]
            if q["id"] == "question:SGN_PREMIERE"
        )
        c["contract_id"] = "P0-CONTEXT-EXERCISE-1.1"
        c["exercise_focus_selection"] = {
            "source_question_ref": q["id"],
            "source_question_sha256": fingerprint(q),
            "local_question_label": LOCAL_LABEL,
            "authority": LOCAL_FOCUS_AUTHORITY,
        }
        return c

    monkeypatch.setattr(f, "Catalog", Catalog)
    monkeypatch.setattr(f, "context", context)
    return f
