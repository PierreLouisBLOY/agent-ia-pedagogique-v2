"use strict";
// Companion of the existing R4 screen. No provider endpoint or browser storage.
let r4LocalDraft = null;
const r4Local = id => document.getElementById("r4-local-" + id);
function r4LocalDirty() { return Boolean(r4LocalDraft?.dirty); }
function r4LocalEditable() {
  const record = r4Record?.record, bundle = record?.bundle;
  return record?.origin === "LOCAL_APPLICATION" &&
    bundle?.contract_id === "R6-P0-PRODUCTION-LOCAL-CHAPTER-4.0" &&
    bundle.course_chapter?.contract_id === "COURSE-CHAPTER-ASSEMBLY-5.0";
}
function r4LocalEditControls() {
  r4Local("copy").disabled = r4Busy || r4Uncertain || !r4LocalEditable() || Boolean(r4LocalDraft);
  const comparableCoDesign = r4Record?.record?.contract_id === "SAVED-PRODUCTION-P0-CODESIGN-1.0" &&
    Boolean(r4Record.record.codesign && r4Record.record.view?.lineage?.parent_version_ref);
  r4Local("compare").disabled = r4Busy || !(comparableCoDesign || r4Record?.record?.provenance?.LOCAL_EDIT_PARENT_RECORD_SHA256);
  r4Local("parent").disabled = r4Busy || !r4Record?.record?.view?.lineage?.parent_version_ref;
  for (const id of ["question", "prompt", "answer", "rationale", "cancel"])
    r4Local(id).disabled = r4Busy;
  r4Local("save").disabled = r4Busy || r4Uncertain || !r4LocalDraft;
}
function r4LocalOpened() {
  r4LocalDraft = null; r4Local("editor").hidden = true;
  r4Local("diff").replaceChildren();
}
function r4LocalQuestion() {
  if (!r4LocalDraft) return;
  const chapter = r4LocalDraft.parent.record.bundle.course_chapter;
  const id = r4Local("question").value;
  const question = chapter.questions.find(row => row.id === id);
  const answer = chapter.teacher_answers.find(row => row.id === id);
  if (!question || !answer) throw new Error("R4_LOCAL_EDIT_BINDING");
  r4Local("prompt").value = question.prompt;
  r4Local("answer").value = answer.expected_answer;
  r4Local("rationale").value = answer.rationale;
  r4LocalDraft.questionId = id; r4LocalDraft.dirty = false;
}
r4Local("copy").addEventListener("click", () => {
  if (r4Busy || r4Uncertain || !r4LocalEditable() || r4LocalDraft) return;
  r4LocalDraft = {parent: r4Record, actionId: "action:" + crypto.randomUUID().replaceAll("-", ""), dirty: false};
  const selector = r4Local("question"); selector.replaceChildren();
  for (const question of r4Record.record.bundle.course_chapter.questions) {
    const option = document.createElement("option"); option.value = question.id;
    option.textContent = "Question " + question.number + " — " + question.prompt.slice(0, 90);
    selector.append(option);
  }
  r4LocalQuestion(); r4Local("editor").hidden = false;
  r4Local("prompt").focus(); r4Controls();
  r4Status.textContent = "Copie brouillon non sauvegardée. Modifiez la consigne et son corrigé puis enregistrez la copie.";
});
r4Local("question").addEventListener("change", () => {
  if (r4LocalDirty() && !window.confirm("Abandonner les modifications non sauvegardées de cette question ?")) {
    r4Local("question").value = r4LocalDraft.questionId; return;
  }
  r4LocalQuestion();
});
for (const id of ["prompt", "answer", "rationale"])
  r4Local(id).addEventListener("input", () => { if (r4LocalDraft) r4LocalDraft.dirty = true; });
r4Local("cancel").addEventListener("click", () => {
  if (r4LocalDirty() && !window.confirm("Abandonner cette copie non sauvegardée ?")) return;
  r4LocalOpened(); r4Controls(); r4Status.textContent = "Copie non sauvegardée abandonnée. La version conservée reste intacte.";
});
r4Local("editor").addEventListener("submit", event => {
  event.preventDefault();
  r4Run(async () => {
    const draft = r4LocalDraft;
    if (!draft || r4Record !== draft.parent) throw new Error("R4_LOCAL_PARENT_CHANGED");
    const selected = draft.parent.record.view;
    const result = await r4Fetch(r4Base() + "/saved-edit", {
      action_id: draft.actionId, record_sha256: draft.parent.record_sha256,
      question_id: draft.questionId, prompt: r4Local("prompt").value,
      expected_answer: r4Local("answer").value, rationale: r4Local("rationale").value
    });
    if (!result.saved || result.production_ref !== selected.production_ref ||
        result.parent_version_ref !== selected.version_ref || result.version_ref === selected.version_ref ||
        result.draft_state !== "DRAFT" || result.promotion !== "NOT_PERFORMED")
      throw new Error("R4_LOCAL_CHILD_CHANGED");
    r4LocalOpened(); await r4Refresh();
    r4Versions.value = result.production_ref + "/" + result.version_ref;
    await r4Open();
    if (r4Record.record_sha256 !== result.record_sha256) throw new Error("R4_LOCAL_CHILD_CHANGED");
    r4Status.textContent = "Copie brouillon enregistrée et rouverte. L'original est conservé ; aucune validation héritée. Vous pouvez exporter et comparer au parent.";
  }, true);
});
r4Local("compare").addEventListener("click", () => r4Run(async () => {
  const selected = r4Record, kind = document.getElementById("r4-kind").value;
  const diff = await r4Fetch(r4Base() + "/compare/" + kind);
  if (r4Record !== selected || kind !== document.getElementById("r4-kind").value ||
      diff.record_sha256 !== selected.record_sha256 || diff.kind !== kind)
    throw new Error("R4_LOCAL_DIFF_CHANGED");
  const region = r4Local("diff"); region.replaceChildren();
  appendSearchText(region, "h3", "Comparaison au parent — " + (kind === "student" ? "consignes élève" : "consignes et corrigé professeur"));
  appendSearchText(region, "p", "Version " + diff.parent_version_ref + " → " + diff.version_ref);
  const labels = {content: "Contenu", prompt: "Consigne", expected_answer: "Réponse attendue", rationale: "Justification", vigilance: "Vigilance", remediation: "Remédiation"};
  for (const change of diff.changes) {
    appendSearchText(region, "h4", change.id + " — " + labels[change.field]);
    appendSearchText(region, "p", "Avant : " + change.before);
    appendSearchText(region, "p", "Après : " + change.after);
  }
  if (!diff.changes.length) appendSearchText(region, "p", "Aucun changement dans cette audience.");
}));
r4Local("parent").addEventListener("click", () => r4Run(async () => {
  const view = r4Record?.record?.view, parent = view?.lineage?.parent_version_ref;
  if (!parent) throw new Error("R4_COMPARISON_UNAVAILABLE");
  r4Versions.value = view.production_ref + "/" + parent;
  await r4Open();
}));
document.getElementById("r4-kind").addEventListener("change", () => {
  r4Local("diff").replaceChildren(); document.getElementById("r4-preview-content").replaceChildren();
});
window.addEventListener("beforeunload", event => {
  if (r4LocalDirty()) { event.preventDefault(); event.returnValue = ""; }
});
r4LocalEditControls();
