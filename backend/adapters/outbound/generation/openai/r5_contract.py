"""R5-only pedagogical instructions; neither output format nor live authority."""
from collections.abc import Mapping, Sequence

from backend.agent_runtime.agents.generation import GenerationPortRequest
from backend.modules.pedagogical_design.contracts.dto.conversation_draft import (
    LOCAL_REFERENCE_LABEL,
    SYNTHETIC_REFERENCE_LABEL,
)

INSTRUCTIONS = """
R5 pedagogical reasoning: preserve the confirmed objectives, level, difficulty,
duration and points. STANDARD is not a numerical level. First construct and verify
a complete useful solution from final objective through components, subcalculations,
classifications and required document data; then choose which aggregates and guidance
the learner receives. Direct application, partial reconstruction and deeper
reconstruction are design reference points, not new API values, three required
variants or an output format. Do not force a preclassified functional balance sheet
to hide missing methodology. Do not require irrelevant adjustments either.
Each necessary operation needs sufficient data, a justified method, compatible units
and dates, no double counting, and a check. A less guided subject still needs an
explicit solution. Distinguish supplied facts, derived results and fictional case
data. Fictional data never replace missing methodological evidence. Cite only what
the supplied passages actually support, not a title, implied authority or your own
knowledge attributed to a source. Several passages may jointly support a method.
If a necessary method or datum is missing, return INSUFFICIENT_EVIDENCE with the
concrete missing dependency, rather than lowering difficulty or inventing a source.
Preserve the requested five-section subject format; this is not a separately
validated correction/marking bundle. No extra graph, infographic or variants.
"""


def instructions_for(request: GenerationPortRequest) -> str:
    evidence = request.resolved_inputs.get("evidence")
    if not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes)):
        return ""  # Legacy non-R5 requests retain their existing mapping behavior.
    labels = {item.get("provenance_label") for item in evidence if isinstance(item, Mapping)}
    if len(evidence) != sum(isinstance(item, Mapping) for item in evidence):
        raise ValueError("R5_PROVENANCE_REJECTED")
    if labels == {LOCAL_REFERENCE_LABEL}:
        return INSTRUCTIONS
    if labels <= {SYNTHETIC_REFERENCE_LABEL, None}:
        return ""
    raise ValueError("R5_PROVENANCE_REJECTED")
