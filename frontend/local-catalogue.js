"use strict";

document.getElementById("organization-search-form")?.addEventListener("submit", async event => {
  event.preventDefault(); const out=document.getElementById("organization-search-result"); out.replaceChildren();
  try {
    const result=await p0Fetch("/api/v2/p0/organization-search", {
      notion_ref:document.getElementById("organization-search-notion").value.trim(),
      sector:document.getElementById("organization-search-sector").value.trim(),
      organization_type:document.getElementById("organization-search-type").value});
    for (const item of result.items) {
      for (const fact of item.documented_facts) {
        appendSearchText(out,"h3",fact.organization_label); appendSearchText(out,"p",fact.fact);
        appendSearchText(out,"p",fact.source_url+" · "+fact.retrieved_on+" · "+fact.license+" · "+fact.reuse_scope);
      }
      for (const analysis of item.local_analysis) appendSearchText(out,"p","Analyse locale du classement : "+analysis.text);
    }
    appendSearchText(out,"p",result.items.length+" résultat(s). Aucune admission canonique ni ajout à la demande.");
  } catch (error) {appendSearchText(out,"p","Recherche locale refusée : "+error.message);}
});

document.getElementById("p0-local-propose")?.addEventListener("click", () => p0Run(async () => {
  const prepared = p0.prepared;
  if (!prepared) throw new Error("P0_PREPARATION_REQUIRED");
  const result = await p0Fetch("/api/v2/p0/local-propose", {command_id:p0Command(),
    preparation_ref:prepared.preparation_ref, preparation_sha256:prepared.preparation_sha256});
  p0.prepared=null; p0.teacher=null; p0ClearConsent(); p0Render(result.view, result.agentic?.quality);
  p0Element("status").textContent="Exercice local de lecture critique prêt à relire. Le passage n’est pas transformé en cours disciplinaire. Aucun envoi.";
  uxMessage("assistant",p0Element("status").textContent); uxShow("prepare");
}));
document.getElementById("organization-capture-form").addEventListener("submit", async event => {
  event.preventDefault();
  const output = document.getElementById("organization-capture-result");
  const siren = document.getElementById("organization-siren").value.trim();
  if (!/^[0-9]{9}$/.test(siren)) return;
  output.replaceChildren();
  appendSearchText(output, "p", "Consultation de la capture locale…");
  try {
    const result = await p0Fetch("/api/v2/p0/organizations/siren:" + siren);
    output.replaceChildren();
    for (const row of result.items) {
      appendSearchText(output, "h3", row.organization_label);
      appendSearchText(output, "p", "Fait documentaire : " + row.fact);
      appendSearchText(output, "p", "Capture consultée le " + row.retrieved_on + " · " + row.publisher);
      appendSearchText(output, "p", row.source_url);
      appendSearchText(output, "p", row.license + " · " + row.reuse_scope);
    }
    appendSearchText(output, "p", "Proposition documentaire à examiner. Son admission et son adéquation aux notions restent à vérifier ; aucune source n’est ajoutée à la demande.");
  } catch (error) {
    output.replaceChildren();
    appendSearchText(output, "p", "Capture locale indisponible : " + (error.message || "consultation refusée"));
  }
});
