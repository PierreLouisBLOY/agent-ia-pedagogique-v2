"use strict";

const form = document.getElementById("resource-form");
const referenceInput = document.getElementById("resource-ref");
const button = document.getElementById("submit-button");
const statusText = document.getElementById("request-status");
const result = document.getElementById("resource-result");
const correlationText = document.getElementById("request-correlation");

const publicMessages = Object.freeze({
  READ15_REQUEST_REJECTED: "La référence ou la requête n'est pas valide.",
  SEARCH_REQUEST_REJECTED: "Saisissez 1 à 12 mots (64 caractères par mot, 256 au total).",
  RES_NOT_FOUND: "Aucune ressource ne correspond à cette référence.",
  ROUTE_NOT_FOUND: "Cette consultation n'est pas disponible.",
  METHOD_REJECTED: "Cette action n'est pas autorisée.",
  HOST_REJECTED: "La frontière locale a refusé cette requête.",
  ORIGIN_REJECTED: "L'origine de cette requête n'est pas autorisée.",
  PREFLIGHT_REJECTED: "Cette requête inter-origines n'est pas autorisée.",
  INTERNAL_ERROR: "La consultation a échoué. Aucune donnée n'a été modifiée."
});

const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-q");
const searchStatus = document.getElementById("search-status");
const searchResults = document.getElementById("search-results");
const searchWindow = document.getElementById("search-window");
let searchController = null;
let searchSequence = 0;

function appendSearchText(parent, tag, text, className = "") {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  parent.append(element);
}

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!searchForm.reportValidity()) return;
  if (searchController) searchController.abort();
  searchController = new AbortController();
  const sequence = ++searchSequence;
  searchResults.replaceChildren();
  searchWindow.hidden = true;
  searchForm.setAttribute("aria-busy", "true");
  searchStatus.textContent = "Recherche en cours…";
  try {
    const parameters = new URLSearchParams({ q: searchInput.value, limit: "10" });
    const response = await fetch("/api/v2/search?" + parameters.toString(), {
      method: "GET", credentials: "omit", cache: "no-store", redirect: "error",
      signal: searchController.signal
    });
    const envelope = await response.json();
    if (sequence !== searchSequence) return;
    if (!response.ok) {
      searchStatus.textContent = publicMessages[envelope?.error?.code] || publicMessages.INTERNAL_ERROR;
      return;
    }
    const data = envelope.data;
    if (!data || !Array.isArray(data.items) || data.items.length > 10 ||
        typeof data.window_full !== "boolean" || typeof data.more_admitted_in_window !== "boolean") {
      throw new Error("INVALID_PUBLIC_RESPONSE");
    }
    const fragment = document.createDocumentFragment();
    for (const item of data.items) {
      if (typeof item.excerpt !== "string" || typeof item.object_ref !== "string" ||
          typeof item.passage_ref !== "string" || typeof item.object_kind !== "string" ||
          typeof item.version_or_checksum !== "string" || item.provenance?.channel !== "LEXICAL" ||
          item.provenance?.authority_absolute !== false || item.provenance?.admission_policy !== "F2A") {
        throw new Error("INVALID_PUBLIC_RESPONSE");
      }
      const row = document.createElement("li");
      appendSearchText(row, "h3", item.read15?.canonical_title || "Passage · " + item.object_kind);
      appendSearchText(row, "p", item.excerpt + (item.excerpt_truncated ? "…" : ""));
      appendSearchText(row, "p", "Objet : " + item.object_ref + " · Passage : " + item.passage_ref +
        " · Version : " + item.version_or_checksum, "provenance");
      appendSearchText(row, "p", "LEXICAL · Admission F2A · Passage courant · Contenu non fiable. " +
        "Le rang ne constitue pas un score de qualité.", "provenance");
      if (item.open_status === "OPENABLE" && item.object_kind === "RESOURCE" &&
          item.read15?.resource_ref === item.object_ref) {
        const openButton = document.createElement("button");
        openButton.type = "button";
        openButton.textContent = "Ouvrir la ressource";
        openButton.addEventListener("click", () => {
          if (activeRequest) return;
          referenceInput.value = item.read15.resource_ref;
          form.requestSubmit();
        });
        row.append(openButton);
      } else {
        appendSearchText(row, "p", "Ce passage n'est pas une ressource ouvrable par READ-15.");
      }
      fragment.append(row);
    }
    searchResults.replaceChildren(fragment);
    searchWindow.hidden = !(data.window_full || data.more_admitted_in_window);
    searchStatus.textContent = data.items.length ? data.items.length + " passage(s) trouvé(s)." :
      "Aucun passage admis dans cette fenêtre. Cela ne signifie pas qu'aucune ressource n'existe.";
  } catch (error) {
    if (sequence !== searchSequence || error?.name === "AbortError") return;
    searchStatus.textContent = "Le service local est indisponible ou sa réponse a été refusée.";
  } finally {
    if (sequence === searchSequence) searchForm.setAttribute("aria-busy", "false");
  }
});
const dataFields = ["availability_status", "canonical_title", "resource_ref", "resource_type"];
let activeRequest = false;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (activeRequest || !form.reportValidity()) return;
  activeRequest = true;
  button.disabled = true;
  result.hidden = true;
  correlationText.hidden = true;
  statusText.textContent = "Consultation en cours…";
  try {
    const response = await fetch(
      "/api/v2/resources/" + encodeURIComponent(referenceInput.value),
      { method: "GET", credentials: "omit", cache: "no-store", redirect: "error" }
    );
    const envelope = await response.json();
    const correlation = envelope?.meta?.correlation_id;
    if (typeof correlation === "string" && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(correlation)) {
      correlationText.textContent = "Corrélation : " + correlation;
      correlationText.hidden = false;
    }
    if (!response.ok) {
      statusText.textContent = publicMessages[envelope?.error?.code] || publicMessages.INTERNAL_ERROR;
      return;
    }
    const data = envelope.data;
    if (!data || Object.keys(data).sort().join(",") !== dataFields.join(",") ||
        dataFields.some((key) => typeof data[key] !== "string" || data[key].length === 0)) {
      throw new Error("INVALID_PUBLIC_RESPONSE");
    }
    document.getElementById("result-title").textContent = data.canonical_title;
    document.getElementById("result-ref").textContent = data.resource_ref;
    document.getElementById("result-type").textContent = data.resource_type;
    document.getElementById("result-availability").textContent = data.availability_status;
    result.hidden = false;
    statusText.textContent = "Consultation terminée.";
  } catch {
    statusText.textContent = "Le service local est indisponible ou sa réponse a été refusée.";
  } finally {
    activeRequest = false;
    button.disabled = false;
  }
});

const conversationForm = document.getElementById("conversation-form");
const contextForm = document.getElementById("context-form");
const conversationStatus = document.getElementById("conversation-status");
const contextFields = document.getElementById("context-fields");
const generationButton = document.getElementById("conversation-generate");
const confirmButton = document.getElementById("context-confirm");
const sendButton = document.getElementById("conversation-send");
const stopWaitButton = document.getElementById("conversation-stop-wait");
const readProductionButton = document.getElementById("production-read");
let conversation = null;
let transportNonce = null;
let commandPending = false;
let commandUncertain = false;
let waiting = false;
let pollTimer = null;
let conversationSequence = 0;
const contextDefinitions = [
  ["resource_type", "Type", ["ASSESSMENT"]],
  ["level", "Niveau", ["BTS_CG_YEAR_1", "BTS_CG_YEAR_2", "FIRST_STMG", "FINAL_STMG"]],
  ["discipline", "Discipline"], ["topics", "Notions (une par ligne)"],
  ["objectives", "Objectifs (un par ligne)"],
  ["difficulty", "Difficulté", ["GUIDED", "STANDARD", "ADVANCED"]],
  ["duration_minutes", "Durée en minutes"], ["total_points", "Note sur"], ["language", "Langue", ["fr"]]
];
const contextInputs = new Map();
for (const [key, labelText, choices] of contextDefinitions) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement(choices ? "select" :
    (key === "topics" || key === "objectives" ? "textarea" : "input"));
  input.id = "context-" + key;
  input.required = true;
  input.autocomplete = "off";
  if (choices) {
    for (const value of ["", ...choices]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value || "À préciser";
      input.append(option);
    }
  }
  label.append(input);
  contextFields.append(label);
  contextInputs.set(key, input);
}
const conversationErrors = Object.freeze({
  R2_NOT_ENABLED: "R2 n’est pas activé pour ce processus.",
  GENERATION_NOT_AUTHORIZED: "Aucun appel fournisseur n’est autorisé sur cette baseline.",
  CONTEXT_CLARIFICATION_REQUIRED: "Précisez les champs manquants ou contradictoires.",
  CONTEXT_NOT_CONFIRMED: "Confirmez le contexte avant de générer.",
  REVISION_CONFLICT: "La conversation a évolué : actualisez son état avant une nouvelle commande.",
  IDEMPOTENCY_CONFLICT: "Cette commande ne peut pas être réutilisée avec un autre contenu.",
  GENERATION_IN_PROGRESS: "Un travail est déjà en cours. Consultez son état.",
  GENERATION_OUTCOME_UNKNOWN: "Résultat incertain : aucun nouvel appel ne doit être lancé.",
  CONVERSATION_EXPIRED: "Cette conversation a expiré après 2 heures.",
  SESSION_CAPACITY_REACHED: "La capacité de cette session est atteinte.",
  INSUFFICIENT_EVIDENCE: "Les supports admis sont insuffisants. Aucune candidate publiée.",
  GENERATION_OUTPUT_INVALID: "La sortie a été refusée. L’ancienne candidate reste inchangée."
});

function updateConversation(view) {
  if (!view || !/^conv:[0-9a-f]{32}$/.test(view.conversation_id) ||
      !Number.isInteger(view.revision) || !Array.isArray(view.messages) || view.messages.length > 40 ||
      typeof view.context?.values !== "object") throw new Error("INVALID_PUBLIC_RESPONSE");
  conversation = view;
  const fragment = document.createDocumentFragment();
  for (const message of view.messages) {
    const row = document.createElement("li");
    row.className = message.role === "USER" ? "conversation-user" : "conversation-assistant";
    row.textContent = (message.role === "USER" ? "Vous : " : "Atelier : ") + message.text;
    fragment.append(row);
  }
  document.getElementById("conversation-messages").replaceChildren(fragment);
  for (const [key, input] of contextInputs) {
    const value = view.context.values[key];
    input.value = Array.isArray(value) ? value.join("\n") : (value ?? "");
  }
  const active = view.active_generation?.state;
  const blocked = commandPending || commandUncertain || active === "IN_PROGRESS" || active === "UNKNOWN";
  sendButton.disabled = blocked;
  confirmButton.disabled = blocked || view.messages.length === 0;
  generationButton.disabled = blocked || view.context.status !== "CONFIRMED";
  readProductionButton.disabled = !view.current_candidate;
  document.getElementById("conversation-limits").textContent = "Champs à préciser : " +
    (view.missing_fields.join(", ") || "aucun") + " · Expiration : " + view.expiration;
  conversationStatus.textContent = active === "IN_PROGRESS" ? "Génération en cours…" :
    active === "UNKNOWN" ? conversationErrors.GENERATION_OUTCOME_UNKNOWN :
    active === "CANDIDATE_READY" ? "Candidate disponible — NON VALIDÉE." :
    view.active_generation?.error_code ? (conversationErrors[view.active_generation.error_code] || "Travail arrêté.") :
    view.context.status === "CONFIRMED" ? "Contexte confirmé. Génération distincte et conditionnelle." :
    "Précisez puis confirmez le contexte.";
}

async function conversationFetch(path, options = {}) {
  const response = await fetch(path, {
    method: "GET", credentials: "omit", cache: "no-store", redirect: "error", ...options,
    headers: { "X-Local-Intent": "conversation-v1", ...options.headers }
  });
  const value = await response.json();
  if (value?.meta?.contract_id !== "CONVERSATION-HTTP-LOCAL-1.0") throw new Error("INVALID_PUBLIC_RESPONSE");
  return { response, value };
}

async function refreshConversation() {
  const sequence = ++conversationSequence;
  try {
    const { response, value } = await conversationFetch("/api/v2/conversation");
    if (sequence !== conversationSequence) return;
    if (!response.ok) {
      conversationStatus.textContent = conversationErrors[value?.error?.code] || "La lecture locale a été refusée.";
      waiting = false;
      return;
    }
    if (!/^[A-Za-z0-9_-]{43}$/.test(value.data.transport_nonce)) throw new Error("INVALID_NONCE");
    transportNonce = value.data.transport_nonce;
    updateConversation(value.data.conversation);
    if (conversation.active_generation?.state !== "IN_PROGRESS") waiting = false;
  } catch {
    conversationStatus.textContent = "Service local indisponible. Aucun renvoi automatique de commande.";
    waiting = false;
  } finally {
    stopWaitButton.disabled = !waiting;
    if (waiting) pollTimer = setTimeout(refreshConversation, 500);
  }
}

async function submitConversation(operation, fields) {
  if (!conversation || commandPending || commandUncertain) return;
  commandPending = true;
  generationButton.disabled = sendButton.disabled = confirmButton.disabled = true;
  const body = { command_id: crypto.randomUUID(), conversation_id: conversation.conversation_id,
    expected_revision: conversation.revision, ...fields };
  try {
    const { response, value } = await conversationFetch("/api/v2/conversation/" + operation, {
      method: "POST", headers: { "Content-Type": "application/json; charset=utf-8", "X-R2-Nonce": transportNonce },
      body: JSON.stringify(body)
    });
    commandPending = false;
    if (!response.ok) {
      conversationStatus.textContent = conversationErrors[value?.error?.code] || "Commande refusée : vérifiez les champs.";
      await refreshConversation();
      conversationStatus.textContent = conversationErrors[value?.error?.code] || "Commande refusée : vérifiez les champs.";
      return;
    }
    if (operation === "generations") {
      waiting = true;
      await refreshConversation();
    } else {
      updateConversation(value.data);
      document.getElementById("conversation-text").value = "";
    }
  } catch {
    commandPending = false;
    commandUncertain = true;
    conversationStatus.textContent = "Réponse perdue : actualisez l’état. Aucun POST ne sera renvoyé automatiquement.";
  }
}
conversationForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (conversationForm.reportValidity()) submitConversation("messages", {
    text: document.getElementById("conversation-text").value
  });
});
contextForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!contextForm.reportValidity()) return;
  const patch = {};
  for (const [key, input] of contextInputs) {
    patch[key] = key === "topics" || key === "objectives" ? input.value.split("\n").filter(Boolean) :
      key === "duration_minutes" ? Number(input.value) : input.value;
  }
  submitConversation("messages", { text: "Je confirme ce contexte pédagogique.", context_patch: patch, confirm_context: true });
});
generationButton.addEventListener("click", () => submitConversation("generations", {
  confirmed_context_sha256: conversation?.confirmed_context_sha256
}));
document.getElementById("conversation-refresh").addEventListener("click", () => {
  clearTimeout(pollTimer);
  refreshConversation();
});
stopWaitButton.addEventListener("click", () => {
  waiting = false;
  clearTimeout(pollTimer);
  stopWaitButton.disabled = true;
  conversationStatus.textContent = "Attente arrêtée. Le travail serveur et son éventuelle facturation ne sont pas annulés.";
});
readProductionButton.addEventListener("click", async () => {
  const refs = conversation?.current_candidate;
  if (!refs || !/^prod:[0-9a-f]{32}$/.test(refs.production_ref) || !/^ver:[0-9a-f]{32}$/.test(refs.version_ref)) return;
  try {
    const { response, value } = await conversationFetch("/api/v2/productions/" +
      encodeURIComponent(refs.production_ref) + "/versions/" + encodeURIComponent(refs.version_ref));
    const data = value.data;
    if (!response.ok || data?.validation_state !== "CANDIDATE" || data.production_ref !== refs.production_ref ||
        data.version_ref !== refs.version_ref || !Array.isArray(data.sections) || data.sections.length !== 5) {
      throw new Error("INVALID_PUBLIC_RESPONSE");
    }
    const fragment = document.createDocumentFragment();
    appendSearchText(fragment, "p", refs.production_ref + " · " + refs.version_ref, "provenance");
    appendSearchText(fragment, "p", data.content);
    for (const section of data.sections) {
      appendSearchText(fragment, "h3", section.section_id);
      appendSearchText(fragment, "p", section.text, "production-section");
    }
    for (const ref of data.references) appendSearchText(fragment, "p",
      ref.evidence_id + " · " + ref.provenance_label + " · " + (ref.declared_used ? "Utilisation déclarée" : "Fourni, non déclaré utilisé"), "provenance");
    for (const limitation of data.limitations) appendSearchText(fragment, "p", limitation, "scope-note");
    document.getElementById("production-content").replaceChildren(fragment);
    document.getElementById("production-result").hidden = false;
  } catch {
    conversationStatus.textContent = "Lecture de cette version refusée. Aucune génération relancée.";
  }
});
refreshConversation();

// R3: no persistent browser store, promotion, export, or implicit POST retry.
const r3Status = document.getElementById("r3-status");
const r3Content = document.getElementById("r3-content");
const r3Version = document.getElementById("r3-version");
let r3State = null;
let r3Busy = false;
let r3Uncertain = false;
let r3ReadSequence = 0;
const r3Buttons = ["prepare", "review", "validate", "modify"];

function r3Controls() {
  const blocked = !r3State || r3Busy || r3Uncertain || commandPending || commandUncertain;
  for (const name of r3Buttons) document.getElementById("r3-" + name).disabled = blocked;
  if (r3State && !blocked) {
    document.getElementById("r3-prepare").disabled = r3State.bundle !== null;
    document.getElementById("r3-review").disabled = r3State.bundle === null;
    document.getElementById("r3-modify").disabled = r3State.bundle === null ||
      r3State.current_candidate?.version_ref !== r3State.version_ref;
  }
}

async function r3Fetch(path, body = null) {
  const options = { method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
    redirect: "error", headers: { "X-Local-Intent": "conversation-v1" } };
  if (body) {
    options.headers["Content-Type"] = "application/json; charset=utf-8";
    options.headers["X-R2-Nonce"] = transportNonce;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const envelope = await response.json();
  if (envelope?.meta?.contract_id !== "REVIEW-MODIFY-HTTP-LOCAL-1.0")
    throw new Error("INVALID_R3_RESPONSE");
  if (!response.ok) throw new Error(envelope?.error?.code || "R3_REFUSED");
  return envelope.data;
}

async function showR3(productionRef, versionRef) {
  const sequence = ++r3ReadSequence;
  if (!/^prod:[0-9a-f]{32}$/.test(productionRef) || !/^ver:[0-9a-f]{32}$/.test(versionRef))
    throw new Error("INVALID_VERSION");
  const base = "/api/v2/productions/" + productionRef + "/versions/" + versionRef;
  const data = await r3Fetch(base + "/assessment");
  const subject = await conversationFetch(base);
  if (sequence !== r3ReadSequence) return;
  if (!subject.response.ok || subject.value.data.production_ref !== productionRef ||
      subject.value.data.version_ref !== versionRef) throw new Error("VERSION_READ_REFUSED");
  if (data.production_ref !== productionRef || data.version_ref !== versionRef ||
      !Array.isArray(data.versions) || data.versions.length > 3 ||
      !["REVIEWED", "REVIEW_NOT_RUN"].includes(data.review_status)) throw new Error("INVALID_R3_STATE");
  r3State = data;
  r3Version.replaceChildren();
  for (const [index, refs] of data.versions.entries()) {
    const option = document.createElement("option");
    option.value = refs.version_ref;
    option.textContent = "V" + (index + 1) + " · " + refs.version_ref;
    option.selected = refs.version_ref === versionRef;
    r3Version.append(option);
  }
  document.getElementById("r3-identities").textContent =
    "Consultée : " + versionRef + " · Courante : " + (data.current_candidate?.version_ref || "aucune");
  r3Content.replaceChildren();
  appendSearchText(r3Content, "h3", "Sujet — version exacte");
  appendSearchText(r3Content, "pre", subject.value.data.content ||
    subject.value.data.production?.content || data.bundle?.subject?.content || "Lire via CAP-R02.");
  if (data.bundle) {
    appendSearchText(r3Content, "h3", "Correction");
    for (const answer of data.bundle.correction.answers)
      appendSearchText(r3Content, "p", answer.question_id + " · " + answer.expected_answer);
    appendSearchText(r3Content, "h3", "Barème · " + data.bundle.marking.total_points + " points");
    appendSearchText(r3Content, "pre", JSON.stringify(data.bundle.marking.dossiers, null, 2));
  }
  appendSearchText(r3Content, "h3", "Review : " + data.review_status);
  appendSearchText(r3Content, "pre", JSON.stringify(data.reviews, null, 2));
  appendSearchText(r3Content, "h3", "Validation déterministe");
  appendSearchText(r3Content, "pre", JSON.stringify(data.validations, null, 2));
  r3Status.textContent = "CANDIDATE — NON VALIDÉE · " + data.review_status;
  r3Controls();
}

document.getElementById("r3-load").addEventListener("click", async () => {
  try {
    await refreshConversation();
    const refs = conversation?.current_candidate;
    if (!refs) throw new Error("NO_CANDIDATE_IN_SESSION");
    await showR3(refs.production_ref, refs.version_ref);
  } catch { r3Status.textContent = "Aucune version R3 disponible. Aucun appel ou renvoi automatique."; }
});
r3Version.addEventListener("change", async () => {
  try { if (r3State) await showR3(r3State.production_ref, r3Version.value); }
  catch { r3Status.textContent = "Version exacte indisponible."; }
});

async function r3Command(operation) {
  if (!r3State || r3Busy || r3Uncertain || commandPending || commandUncertain) return;
  r3Busy = true;
  r3Controls();
  let submitted = false;
  try {
    await refreshConversation();
    const state = r3State;
    const body = { conversation_id: conversation.conversation_id, command_id: crypto.randomUUID(),
      expected_revision: conversation.revision, production_ref: state.production_ref };
    if (operation === "modifications") {
      Object.assign(body, { base_version_ref: state.version_ref, base_bundle_sha256: state.bundle_sha256,
        operation: "HARDEN_DOSSIER_3", instruction: "Rends le dossier 3 plus difficile." });
    } else {
      body.version_ref = state.version_ref;
      if (operation === "assessment-preparations") body.subject_sha256 = state.subject_sha256;
      else body.bundle_sha256 = state.bundle_sha256;
      if (operation === "reviews") body.dimensions = ["REV-ACC", "REV-CON", "REV-PED"];
    }
    submitted = true;
    let result = await r3Fetch("/api/v2/conversation/" + operation, body);
    if (!/^op:[0-9a-f]{32}$/.test(result.operation_ref)) throw new Error("INVALID_OPERATION");
    const deadline = Date.now() + 90000;
    while (result.state === "RUNNING" && Date.now() < deadline) {
      r3Status.textContent = "Travail R3 en cours. Aucune répétition de commande.";
      await new Promise(resolve => setTimeout(resolve, 1000));
      result = await r3Fetch("/api/v2/conversation/operations/" + result.operation_ref);
    }
    if (result.state === "RUNNING" || result.state === "UNKNOWN") {
      r3Uncertain = true;
      throw new Error("R3_UNKNOWN");
    }
    await showR3(result.production_ref, result.version_ref);
    if (result.state !== "SUCCEEDED") r3Status.textContent = "Travail refusé ; version antérieure conservée.";
    if (operation === "modifications" && result.state === "FAILED_OUTPUT" &&
        result.error_code === "DEPENDENCY_CHANGE_REQUIRES_APPROVAL")
      r3Status.textContent = "Modification refusée : le changement de durée ou de points de D3 exige un accord distinct. La version précédente est conservée.";
  } catch {
    if (submitted) r3Uncertain = true;
    r3Status.textContent = "Travail refusé ou résultat incertain. Aucun renvoi automatique.";
  } finally {
    r3Busy = false;
    r3Controls();
  }
}
for (const [name, operation] of [["prepare", "assessment-preparations"], ["review", "reviews"],
    ["validate", "validations"], ["modify", "modifications"]]) {
  document.getElementById("r3-" + name).addEventListener("click", () => r3Command(operation));
}

// R4: a saved document is not a restored session. No automatic command replay.
let r4Nonce = "";
let r4Record = null;
let r4Busy = false;
let r4Uncertain = false;
const r4Status = document.getElementById("r4-status");
const r4Versions = document.getElementById("r4-version");
function r4Base() {
  const view = r4Record?.record?.view;
  if (!view) throw new Error("R4_NOT_OPEN");
  return "/api/v2/productions/" + view.production_ref + "/versions/" + view.version_ref;
}
function r4Controls() {
  for (const id of ["r4-preview", "r4-download", "r4-validate", "r4-promote"])
    document.getElementById(id).disabled = r4Busy || !r4Record ||
      (["r4-validate", "r4-promote"].includes(id) &&
       (r4Uncertain || r4Record.record.origin !== "LOCAL_APPLICATION"));
  document.getElementById("r4-save").disabled = r4Busy || r4Uncertain || !r4Nonce;
}
async function r4Fetch(path, body = null, binary = false) {
  const options = {method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
    redirect: "error", headers: {"X-Local-Intent": "conversation-v1"}};
  if (body) {
    options.headers["Content-Type"] = "application/json; charset=utf-8";
    options.headers["X-R2-Nonce"] = r4Nonce;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  if (binary && response.ok) {
    if (response.headers.get("Content-Type") !== "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
      throw new Error("R4_INVALID_DOCUMENT");
    return response.blob();
  }
  const envelope = await response.json();
  if (!response.ok || envelope?.meta?.contract_id !== "SAVE-REOPEN-WORD-HTTP-LOCAL-1.0")
    throw new Error(envelope?.error?.code || "R4_REFUSED");
  return envelope.data;
}
async function r4Refresh() {
  const data = await r4Fetch("/api/v2/conversation/saved");
  r4Nonce = data.transport_nonce;
  const selected = r4Versions.value;
  r4Versions.replaceChildren();
  for (const version of data.versions) {
    const option = document.createElement("option");
    option.value = version.production_ref + "/" + version.version_ref;
    option.textContent = version.version_ref + " · " + version.origin;
    option.selected = option.value === selected;
    r4Versions.append(option);
  }
  r4Status.textContent = data.versions.length + " version(s) conservée(s) sur disque. Aucune autorité restaurée.";
  r4Controls();
}
async function r4Open() {
  const refs = r4Versions.value.split("/");
  if (refs.length !== 2 || !/^prod:[0-9a-f]{32}$/.test(refs[0]) || !/^ver:[0-9a-f]{32}$/.test(refs[1]))
    throw new Error("R4_INVALID_SELECTION");
  r4Record = await r4Fetch("/api/v2/productions/" + refs[0] + "/versions/" + refs[1] + "/saved");
  const details = document.getElementById("r4-details");
  details.replaceChildren();
  appendSearchText(details, "p", r4Record.status === "PROMOTED" ? "Promotion explicite enregistrée" : "CANDIDATE — NON VALIDÉE");
  appendSearchText(details, "p", "Origine : " + r4Record.record.origin + " · SHA-256 : " + r4Record.record_sha256);
  for (const note of r4Record.record.reservations) appendSearchText(details, "p", note);
  appendSearchText(details, "h3", "Rapports historiques — attachés à cette version uniquement");
  appendSearchText(details, "pre", JSON.stringify({reviews: r4Record.record.reviews, validations: r4Record.record.validations}, null, 2));
  appendSearchText(details, "h3", "Nouvelles actions R4 distinctes");
  appendSearchText(details, "pre", JSON.stringify(r4Record.new_actions, null, 2));
  document.getElementById("r4-preview-content").replaceChildren();
  r4Status.textContent = "Version rouverte. Aucune revalidation automatique ; A16 reste visible.";
  r4Controls();
}
async function r4Run(action, writes = false) {
  if (r4Busy || (writes && r4Uncertain)) return;
  r4Busy = true;
  r4Controls();
  try { await action(); }
  catch (error) {
    if (writes) r4Uncertain = true;
    r4Status.textContent = "Opération refusée ou incertaine : " + error.message + ". Aucun rejeu automatique.";
  } finally { r4Busy = false; r4Controls(); }
}
document.getElementById("r4-refresh").addEventListener("click", () => r4Run(r4Refresh));
document.getElementById("r4-open").addEventListener("click", () => r4Run(r4Open));
document.getElementById("r4-save").addEventListener("click", () => r4Run(async () => {
  if (!r3State) throw new Error("Consultez d’abord une version R3 de la session");
  await r4Fetch("/api/v2/conversation/saved", {production_ref: r3State.production_ref, version_ref: r3State.version_ref});
  await r4Refresh();
  r4Versions.value = r3State.production_ref + "/" + r3State.version_ref;
  await r4Open();
}, true));
document.getElementById("r4-preview").addEventListener("click", () => r4Run(async () => {
  const data = await r4Fetch(r4Base() + "/preview/" + document.getElementById("r4-kind").value);
  const target = document.getElementById("r4-preview-content");
  target.replaceChildren();
  appendSearchText(target, "h3", data.title);
  for (const block of data.blocks) appendSearchText(target, block.style === "Heading1" ? "h4" : "p", block.text);
}));
document.getElementById("r4-download").addEventListener("click", () => r4Run(async () => {
  const kind = document.getElementById("r4-kind").value;
  const data = await r4Fetch(r4Base() + "/word/" + kind, null, true);
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = kind + "-" + r4Record.record.view.version_ref.slice(4) + ".docx";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}));
document.getElementById("r4-validate").addEventListener("click", () => r4Run(async () => {
  await r4Fetch(r4Base() + "/saved-validation", {action_id: "action:" + crypto.randomUUID().replaceAll("-", ""),
    record_sha256: r4Record.record_sha256});
  await r4Open();
}, true));
document.getElementById("r4-promote").addEventListener("click", () => r4Run(async () => {
  const gate = await r4Fetch(r4Base() + "/promotion");
  if (!window.confirm("Promouvoir cette version exacte ? Vous reconnaissez A16, les réserves affichées et la distinction avec une simple sauvegarde.")) return;
  await r4Fetch(r4Base() + "/promotion", {action_id: "action:" + crypto.randomUUID().replaceAll("-", ""),
    record_sha256: gate.record_sha256, gate_id: gate.gate_id,
    confirmation: "PROMOTE_EXACT_VERSION", acknowledge_a16: true});
  await r4Open();
}, true));
r4Run(r4Refresh);
