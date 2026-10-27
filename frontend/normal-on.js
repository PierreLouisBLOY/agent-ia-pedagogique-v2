"use strict";
// Same P0 screen and Application routes; no provider, secret or extra store here.
let p0NormalMode = "NONE";
let p0NormalAsync = false;
let p0FiniteBinding = "DISARMED_NO_MULTI_OPERATION_AUTHORITY";
let p0FinitePreview = null;
let p0FiniteSubmitted = false;
function p0FiniteRemember(command) {
  try { sessionStorage.setItem("v2.finite.command", command); } catch (_) { /* Follow-up remains available by its exact ID. */ }
  p0Element("finite-follow-panel").hidden = false;
  p0Element("finite-follow-status").textContent = "Commande " + command + " conservée pour consultation ; aucun renvoi automatique.";
}
function p0NormalConfigure(metadata) {
  p0FiniteBinding = metadata.codesign_binding || "DISARMED_NO_MULTI_OPERATION_AUTHORITY";
  let retained = null;
  try { retained = sessionStorage.getItem("v2.finite.command"); } catch (_) { /* Storage is optional, never authority. */ }
  if (/^[a-f0-9]{32}$/.test(retained || "")) p0FiniteRemember(retained);
  p0Element("finite-follow").onclick = () => p0Run(async () => {
    let command = null;
    try { command = sessionStorage.getItem("v2.finite.command"); } catch (_) { /* No invented identity. */ }
    if (!/^[a-f0-9]{32}$/.test(command || "")) throw new Error("P0_CHAIN_FOLLOWUP_IDENTITY");
    const observed = await p0Fetch("/api/v2/p0/commands/" + command);
    if (observed.command_id !== command) throw new Error("P0_CHAIN_FOLLOWUP_IDENTITY");
    p0Element("finite-follow-status").textContent = "Commande " + command + " : " + (observed.phase || observed.state) +
      ". Consultation seulement ; aucune autorité restaurée, aucune réservation libérée.";
    if (observed.state === "LOCAL_COMMAND_COMPLETED" && observed.result?.state === "CODESIGN_CANDIDATE") {
      p0Render(observed.result.view); uxShow("prepare");
    }
  });
  const mode = metadata.normal_mode || "NONE";
  if (!["NONE", "PREPARE_ONLY", "ENABLED", "FINITE_CHAIN_ONLY"].includes(mode) ||
      (mode !== "NONE" && metadata.credential_source !== "OPENAI_API_KEY") ||
      (mode === "PREPARE_ONLY" && (metadata.live_binding !== "NONE" || metadata.normal_consent_binding !== "NONE")) ||
      (mode === "ENABLED" && (metadata.live_binding !== "EXPLICIT_PORT" ||
        metadata.normal_consent_binding !== "EXPLICIT_PRODUCT_PERMISSION" ||
        metadata.normal_command_followup !== "EXPLICIT_SINGLE_COMMAND_FOLLOWUP")))
    throw new Error("P0_NORMAL_METADATA_BINDING");
  p0NormalMode = mode;
  p0NormalAsync = mode === "ENABLED";
}
function p0NormalIsProposal() { return p0NormalMode === "PREPARE_ONLY"; }
function p0CoDesignControls() {
  const panel = p0Element("codesign"); panel.hidden = !p0.view;
  p0FinitePreview = null;
  p0Element("codesign-consents").hidden = true;
  p0Element("codesign-body-panel").hidden = true;
  p0Element("codesign-identities").textContent = "";
  p0Element("codesign-status").textContent = "Parcours désarmé. La permission de création seule ne couvre pas la revue et la correction IA.";
  p0Element("codesign-preview").onclick = () => p0Run(async () => {
    const parent = p0Identity();
    if (p0.dirty) throw new Error("P0_CODESIGN_SAVE_LOCAL_EDITS_FIRST");
    const result = await p0Fetch("/api/v2/p0/codesign-preview", {command_id:p0Command(), ...parent,
      direction:p0Element("codesign-direction").value, objective:p0Element("codesign-objective").value.trim(),
      evidence_query:p0Element("codesign-evidence-query").value.trim() || null});
    if (p0DisplayedVersion(parent) && result.state === "BLOCKED") {
      p0Element("codesign-status").textContent = "Parcours bloqué avant tout effet : " + (result.code || "P0_CODESIGN_BLOCKED");
      p0Element("codesign-identities").textContent = JSON.stringify(result, null, 2);
      return;
    }
    if (!p0DisplayedVersion(parent) || !["DISARMED","READY"].includes(result.state) || result.authority !== "NONE" ||
        result.provider_attempts !== 0 || result.bundle_sha256 !== parent.bundle_sha256)
      throw new Error("P0_CODESIGN_PREVIEW_BINDING");
    if (result.schema === "P0-FINITE-CHAIN-PREVIEW-1.0") {
      const bytes = new TextEncoder().encode(result.first_request_body_utf8);
      const pin = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(x => x.toString(16).padStart(2,"0")).join("");
      if (pin !== result.first_request_sha256 || bytes.length !== result.first_request_bytes ||
          result.maximum_effects !== 4 || result.parameters?.retry !== 0 ||
          (result.state === "READY" && p0FiniteBinding !== "FINITE_CHAIN_ENABLED"))
        throw new Error("P0_CHAIN_PREVIEW_BINDING");
      p0FinitePreview = result;
      p0Element("codesign-body-panel").hidden = false;
      p0Element("codesign-body").textContent = result.first_request_body_utf8;
      p0Element("codesign-consents").hidden = result.state !== "READY" || p0FiniteSubmitted;
      p0Element("codesign-transfer").checked = false;
      p0Element("codesign-cost").checked = false;
      p0Element("codesign-final").disabled = true;
      p0Element("codesign-status").textContent = "Premier corps : " + result.first_request_bytes + " octets, SHA-256 " + pin +
        ". Jusqu’à quatre effets : proposition, revue, une correction éventuelle et sa revue. Plafond de la chaîne : " + result.chain_bound_usd +
        " USD. Réservations observées à " + result.snapshot_at_utc + " : " + result.reserved_budget_usd + " USD ; cumul projeté : " + result.projected_cumulative_usd +
        " USD. Les corps suivants seront dérivés des résultats contrôlés, dans les rôles et plafonds présentés. Aucun t0 avant confirmation. Aucun retry après incertitude. La qualité pédagogique reste à apprécier.";
      p0Element("codesign-identities").textContent = JSON.stringify({...result, first_request_body_utf8:undefined}, null, 2);
      return;
    }
    p0Element("codesign-status").textContent = "Recherche de preuves, proposition, contrôle local, revue indépendante et au plus une correction suivie de sa revue. Jusqu’à quatre opérations IA ; coût cumulé et autorisations à établir avant tout envoi. Aucune autorité démarrée.";
    p0Element("codesign-identities").textContent = JSON.stringify(result, null, 2);
  });
  const invalidate = () => {
    p0FinitePreview = null;
    p0Element("codesign-transfer").checked = false;
    p0Element("codesign-cost").checked = false;
    p0Element("codesign-final").disabled = true;
    p0Element("codesign-consents").hidden = true;
  };
  for (const id of ["codesign-direction","codesign-objective","codesign-evidence-query"]) p0Element(id).oninput = invalidate;
  for (const id of ["codesign-transfer","codesign-cost"]) p0Element(id).onchange = () => {
    p0Element("codesign-final").disabled = !p0FinitePreview || p0FiniteSubmitted || !p0DisplayedVersion(p0FinitePreview) ||
      Date.now() >= Date.parse(p0FinitePreview.expires_at_utc) || !p0Element("codesign-transfer").checked || !p0Element("codesign-cost").checked;
  };
  p0Element("codesign-final").onclick = () => p0Run(async () => {
    const preview = p0FinitePreview;
    if (!preview || p0FiniteSubmitted || !p0DisplayedVersion(preview) || !p0Element("codesign-transfer").checked ||
        !p0Element("codesign-cost").checked || Date.now() >= Date.parse(preview.expires_at_utc)) throw new Error("P0_CHAIN_EXACT_CONSENT_REQUIRED");
    p0FiniteSubmitted = true;
    p0Element("codesign-final").disabled = true;
    const command = p0Command();
    p0FiniteRemember(command);
    await p0Fetch("/api/v2/p0/codesign-consent", {command_id:command,
      production_ref:preview.production_ref, version_ref:preview.version_ref, bundle_sha256:preview.bundle_sha256,
      direction:preview.direction, objective:preview.objective, evidence_query:preview.evidence_query,
      preview_sha256:preview.preview_sha256, transfer_accepted:true, cost_bound_accepted:true});
    for (;;) {
      const status = await p0Fetch("/api/v2/p0/commands/" + command);
      if (status.command_id !== command) throw new Error("P0_CHAIN_FOLLOWUP_IDENTITY");
      p0Element("codesign-status").textContent = "Commande " + command + " : " + (status.phase || status.state) + ". Aucun second envoi.";
      if (status.state === "LOCAL_COMMAND_COMPLETED") {
        if (status.result?.state !== "CODESIGN_CANDIDATE") throw new Error("P0_CHAIN_RESULT_REQUIRES_PASSIVE_EXAMINATION");
        p0Render(status.result.view);
        p0Element("status").textContent = "Variante conservée et rouverte ; exports élève et professeur disponibles. Relecture enseignante nécessaire.";
        break;
      }
      if (status.state !== "LOCAL_COMMAND_RUNNING") throw new Error(status.code || "P0_CHAIN_OUTCOME_UNCERTAIN");
      await new Promise(resolve => setTimeout(resolve, 750));
    }
  });
  p0Element("codesign-revoke").onclick = () => p0Run(async () => {
    if (!p0FinitePreview) throw new Error("P0_CHAIN_PREVIEW_REQUIRED");
    await p0Fetch("/api/v2/p0/codesign-revoke", {command_id:p0Command(), preview_sha256:p0FinitePreview.preview_sha256});
    invalidate();
    p0Element("codesign-status").textContent = "Chaîne révoquée ; aucune réservation passée n’est libérée.";
  });
}
function p0NormalFollowup() { return p0NormalAsync; }
function p0NormalControls() {
  if (p0NormalMode === "NONE") return;
  if (p0NormalMode === "FINITE_CHAIN_ONLY") {
    p0Element("generate").disabled = true;
    p0Element("consent-send").disabled = true;
    return;
  }
  for (const id of ["consent-transfer", "consent-cost"])
    p0Element(id).disabled = p0NormalIsProposal() || p0.busy;
  if (p0NormalIsProposal()) {
    p0Element("generate").disabled = p0.busy || p0.uncertain || !p0.nonce || !p0.prepared;
    p0Element("generate").textContent = "Examiner la préparation sans envoi";
    p0Element("consent-send").disabled = true;
  } else if (p0.consent?.remaining_calls === 0) {
    p0Element("consent-send").disabled = true;
  }
}
function p0NormalEnhance() {
  if (p0NormalMode !== "ENABLED") return;
  const summary = p0Element("consent-summary");
  appendSearchText(summary, "p", "Clé utilisée uniquement par le backend depuis OPENAI_API_KEY ; aucune invite console.");
  appendSearchText(summary, "p", "Nouvelle demande indépendante : aucun ancien droit n’est réarmé. UNKNOWN, 406A, 2f1e et 09ce restent distincts, avec leurs réservations et leurs incertitudes. Le plafond présenté couvre ce nouvel appel, pas leur facturation inconnue.");
  appendSearchText(summary, "p", "Vos deux consentements normaux portent sur ce contenu exact et ce coût maximal. La commande finale fixe le début du grant ; aucune tentative automatique après une interruption.");
}
async function p0ShowNormalProposal() {
  const prepared = p0.prepared;
  const result = await p0Fetch("/api/v2/p0/consent-preview", {command_id:p0Command(),
    preparation_ref:prepared.preparation_ref, preparation_sha256:prepared.preparation_sha256});
  if (p0.prepared !== prepared || result.state !== "OWNER_NORMAL_ADOPTION_REQUIRED" ||
      result.schema !== "P0-NORMAL-PREPARATION-PREVIEW-1.0" ||
      result.preparation_sha256 !== prepared.preparation_sha256 || result.preparation_ref !== prepared.preparation_ref ||
      result.effect_enabled !== false || result.authority !== "NONE" || result.provider_attempts !== 0 ||
      result.admission_status !== "OWNER_DECISION_PENDING" || typeof result.request_body_utf8 !== "string" ||
      !p0CostBoundWithinCeiling(result.cost_bound_usd)) throw new Error("P0_NORMAL_PROPOSAL_BINDING");
  const raw = new TextEncoder().encode(result.request_body_utf8);
  const pin = [...new Uint8Array(await crypto.subtle.digest("SHA-256", raw))].map(x => x.toString(16).padStart(2,"0")).join("");
  if (pin !== result.request_sha256 || raw.length !== result.request_bytes) throw new Error("P0_NORMAL_PROPOSAL_BODY_CHANGED");
  p0ClearConsent(); p0Element("consent").hidden = false;
  const region = p0Element("consent-summary");
  appendSearchText(region, "h3", "Préparation sans envoi — décision propriétaire requise");
  appendSearchText(region, "p", "OpenAI · " + result.request_parameters.model + " · https://api.openai.com/v1/responses");
  appendSearchText(region, "p", result.request_bytes + " octets · SHA-256 " + result.request_sha256);
  appendSearchText(region, "p", "Borne calculée : " + result.cost_bound_usd + " USD. Calcul local conservateur ; tarif et tokenizer à rattacher à la décision exacte. Aucune admission supposée.");
  appendSearchText(region, "p", "Aucun consentement enregistré, aucune autorité démarrée, aucun slot ou grant créé. Les sources proposées et leur statut réel figurent ci-dessous.");
  appendSearchText(region, "p", "UNKNOWN, 406A, 2f1e et 09ce restent conservés. Leur résultat et leur facture ne sont pas déduits de ce calcul ; aucune réservation antérieure n’est libérée.");
  p0Element("consent-body").textContent = result.request_body_utf8;
  p0Element("consent-identities").textContent = JSON.stringify({...result, request_body_utf8:undefined}, null, 2);
  p0Element("status").textContent = "Préparation examinable. Adoption/chargement ON puis confirmation personnelle requis ; aucun envoi disponible dans ce mode.";
  p0NormalControls();
}
async function p0FollowPilotCommand(commandId) {
  const deadline = Date.now() + 900000;
  const labels = {PREFLIGHT_RUNNING:"Préflight en cours", PREFLIGHT_CHECKED:"Préflight vérifié",
    BUDGET_RESERVED:"Réservation enregistrée", RESERVED:"Capture de départ conservée",
    TRANSPORT_ENTERED:"Tentative transport engagée ; arrivée fournisseur non établie",
    RESPONSE_CAPTURED:"Réponse capturée", PARSED:"Réponse contrôlée localement"};
  while (Date.now() < deadline) {
    const status = await p0Fetch("/api/v2/p0/commands/" + commandId);
    if (status?.command_id !== commandId) throw new Error("P1_PILOT_FOLLOWUP_IDENTITY_REQUIRED");
    if (status.state === "LOCAL_COMMAND_COMPLETED") {
      if (status.result?.state === "CANDIDATE") return status.result;
      p0.uncertain = true;
      throw Object.assign(new Error("P1_PILOT_FOLLOWUP_RESULT_UNCONFIRMED"), {localCommandId:commandId});
    }
    if (status.state !== "LOCAL_COMMAND_RUNNING")
      throw Object.assign(new Error(status.code || "P1_PILOT_FOLLOWUP_OUTCOME_INDETERMINATE"), {localCommandId:commandId});
    p0Element("status").textContent = (labels[status.phase] || "Création en cours") +
      ". Suivi de la commande " + commandId + " ; aucun second envoi. Clé utilisée uniquement côté backend.";
    await new Promise(resolve => setTimeout(resolve, 750));
  }
  throw Object.assign(new Error("P1_PILOT_FOLLOWUP_STILL_UNCONFIRMED"), {localCommandId:commandId});
}

// Explicit local exercise focus, still using the normal form and routes.
function p0ExerciseQuestionParts(label) {
  if (typeof label !== "string") return [];
  const parts = label.match(/[^?]+\?/gu) || [];
  return parts.join("").trim() === label.trim() && parts.every(p => p.slice(0,-1).trim()) ? parts.map(p => p.trim()) : [];
}
let p0ExerciseFocusIdentity = "";
function p0ExerciseFocusOptions() {
  const exercise = p0Element("family").value === "EXERCISE";
  const structured = exercise && ["STRUCTURED", "CASE_STUDY"].includes(p0Element("exercise-format").value);
  p0Element("exercise-format-panel").hidden = !exercise;
  p0Element("exercise-focus-panel").hidden = !structured;
  p0Element("exercise-focus").required = structured;
  p0Element("exercise-justification").required = structured;
  const frame = p0InstitutionalFrame();
  const question = frame?.questions?.find(q => q.question_ref === p0Element("program-question").value);
  const identity = JSON.stringify([exercise,structured,p0Element("exercise-format").value,p0Element("level").value,frame?.program_version,question?.question_ref,question?.source_question_sha256,question?.label]);
  if (identity === p0ExerciseFocusIdentity) return;
  p0ExerciseFocusIdentity = identity;
  const select = p0Element("exercise-focus"); select.replaceChildren();
  const empty = document.createElement("option"); empty.value="";empty.textContent="Choisir une composante exacte";select.append(empty);
  p0Element("exercise-justification").value="";
  p0Element("exercise-source-label").textContent = question ? "Libellé institutionnel complet : " + question.label : "Sélectionnez d'abord une question du programme.";
  if (structured && /^[a-f0-9]{64}$/.test(question?.source_question_sha256 || "")) {
    const parts = p0ExerciseQuestionParts(question.label);
    for (const part of parts) if (parts.filter(p => p === part).length === 1) {
      const option=document.createElement("option");option.value=part;option.textContent=part;select.append(option);
    }
  }
  select.value="";
  p0Invalidate();
}
