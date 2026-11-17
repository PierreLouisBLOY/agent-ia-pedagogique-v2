// Read-only Application catalogue. Choosing documents never dispatches generation.
let p0DocumentaryCatalogue = null;
function p0DocumentaryEnabled() {
  return !!p0DocumentaryCatalogue && p0Element("documentary-enabled").checked &&
    p0Element("family").value === "COURSE" && p0Element("course-format").value === "CHAPTER";
}
function p0DocumentaryConfigure(catalogue) {
  p0DocumentaryCatalogue = catalogue;
  const select = p0Element("documentary-organization");
  select.replaceChildren(new Option("Choisir Decathlon ou Orange", ""));
  for (const item of catalogue?.organizations || []) select.append(new Option(item.label + " — Groupe", item.id));
  p0DocumentaryOptions();
}
function p0DocumentaryOptions() {
  const panel = p0Element("documentary-panel");
  panel.hidden = !p0DocumentaryCatalogue || p0Element("family").value !== "COURSE" ||
    p0Element("course-format").value !== "CHAPTER";
  const enabled = p0DocumentaryEnabled();
  p0Element("documentary-organization").disabled = !enabled;
  p0Element("documentary-organization").required = enabled;
  if (enabled) p0Element("real-organization-panel").hidden = true;
  for (const box of p0Element("documentary-documents").querySelectorAll("input")) box.disabled = !enabled;
}
function p0DocumentarySelection(context) {
  if (context.course_format !== "CHAPTER" || !p0DocumentaryEnabled()) return undefined;
  const organization_id = p0Element("documentary-organization").value;
  const document_ids = [...p0Element("documentary-documents").querySelectorAll("input:checked")].map(x=>x.value);
  if (!organization_id || !document_ids.length || document_ids.length > 6)
    throw Object.assign(new Error("Choisissez une organisation et de une à six fiches documentaires."), {confirmedRefusal:true});
  return {organization_id, document_ids, archive_sha256:p0DocumentaryCatalogue.archive_sha256,
    snapshot_sha256:p0DocumentaryCatalogue.snapshot_sha256};
}
async function p0DocumentaryInspect(id) {
  const result = await p0Fetch("/api/v2/p0/documentary-library/" + id);
  if (result.snapshot_sha256 !== p0DocumentaryCatalogue.snapshot_sha256 || result.document.id !== id)
    throw new Error("DOCUMENTARY_SELECTION_CHANGED");
  const out = p0Element("documentary-read"); out.replaceChildren();
  appendSearchText(out, "h4", id + " — " + result.document.metadata.title);
  appendSearchText(out, "p", "Synthèse pédagogique locale, non validée par le propriétaire. Périmètre groupe.");
  for (const block of result.document.blocks) {
    if (block.kind === "PARAGRAPH") appendSearchText(out, "p", block.text);
    else {
      const table = document.createElement("table");
      for (const row of block.rows) {
        const tr = document.createElement("tr");
        for (const cell of row) appendSearchText(tr, "td", cell);
        table.append(tr);
      }
      out.append(table);
    }
  }
  appendSearchText(out, "h4", "Sources déclarées du dossier");
  for (const s of result.sources) appendSearchText(out, "p", s.id + " · " + s.publisher + " · " + s.title + "\n" + s.url + "\n" + s.rights_status);
  appendSearchText(out, "p", result.document.metadata.rights_policy);
}
document.addEventListener("DOMContentLoaded", ()=>{
  p0Element("documentary-enabled").addEventListener("change", ()=>{p0Invalidate();p0RealOrganizationOptions();p0DocumentaryOptions();});
  p0Element("documentary-organization").addEventListener("change", ()=>{
    p0Invalidate();
    const out = p0Element("documentary-documents"); out.replaceChildren();
    p0Element("documentary-read").replaceChildren();
    for (const doc of p0DocumentaryCatalogue.documents.filter(d=>d.organization_id === p0Element("documentary-organization").value)) {
      const row = document.createElement("div"), label = document.createElement("label"), box = document.createElement("input");
      box.type = "checkbox"; box.value = doc.id; box.addEventListener("change", p0Invalidate);
      label.append(box, document.createTextNode(doc.id + " — " + doc.title));
      const button = document.createElement("button"); button.type = "button"; button.textContent = "Lire " + doc.id;
      button.addEventListener("click", ()=>p0Run(()=>p0DocumentaryInspect(doc.id)));
      row.append(label, button); out.append(row);
    }
    p0DocumentaryOptions();
  });
});
