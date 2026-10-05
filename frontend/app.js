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
      const trace = document.createElement("details"); trace.className = "secondary";
      appendSearchText(trace, "summary", "Provenance et version");
      appendSearchText(trace, "p", "Objet : " + item.object_ref + " · Passage : " + item.passage_ref +
        " · Version : " + item.version_or_checksum, "provenance");
      appendSearchText(trace, "p", "LEXICAL · Admission F2A · Passage courant · Contenu non fiable. " +
        "Le rang ne constitue pas un score de qualité.", "provenance");
      row.append(trace);
      const selectButton = document.createElement("button");
      selectButton.type = "button";
      selectButton.textContent = "Utiliser ce passage pour ma production";
      selectButton.addEventListener("click", () => {
        p0Element("search-query").value = searchInput.value;
        p0Element("notion-id").value = "";
        p0Element("search-passage").value = item.passage_ref;
        p0Element("search-query").closest("details").open = true;
        p0Invalidate();
        p0Element("status").textContent = "Passage sélectionné. Confirmez le contexte et préparez votre production.";
        uxShow("prepare"); document.getElementById("preparation-parameters").open = true;
        document.getElementById("drawer-sources").textContent = item.excerpt;
        p0Element("heading").scrollIntoView({behavior: "smooth"});
      });
      if (["NOTION", "PEDAGOGICAL_CONTENT", "METHOD", "FRAMEWORK_ELEMENT", "OFFICIAL_OCCURRENCE"].includes(item.object_kind))
        row.append(selectButton);
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

async function localBoundedRequest(path, options, consume) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    return await consume(await fetch(path, {...options, signal: controller.signal}));
  } finally { clearTimeout(timeout); }
}

async function conversationFetch(path, options = {}) {
  return localBoundedRequest(path, {
    method: "GET", credentials: "omit", cache: "no-store", redirect: "error", ...options,
    headers: { "X-Local-Intent": "conversation-v1", ...options.headers }
  }, async response => {
    const value = await response.json();
    if (value?.meta?.contract_id !== "CONVERSATION-HTTP-LOCAL-1.0") throw new Error("INVALID_PUBLIC_RESPONSE");
    return { response, value };
  });
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
  return localBoundedRequest(path, options, async response => {
  if (binary && response.ok) {
    if (response.headers.get("Content-Type") !== "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
      throw new Error("R4_INVALID_DOCUMENT");
    return response.blob();
  }
  const envelope = await response.json();
  if (!response.ok || envelope?.meta?.contract_id !== "SAVE-REOPEN-WORD-HTTP-LOCAL-1.0")
    throw new Error(envelope?.error?.code || "R4_REFUSED");
  return envelope.data;
  });
}
async function r4Refresh() {
  const data = await r4Fetch("/api/v2/conversation/saved");
  r4Nonce = data.transport_nonce;
  const selected = r4Versions.value;
  r4Versions.replaceChildren();
  for (const version of data.versions) {
    const option = document.createElement("option");
    option.value = version.production_ref + "/" + version.version_ref;
    option.textContent = "Version " + (r4Versions.options.length + 1) + (version.origin === "IMPORTED_DOCUMENTARY" ? " · document conservé" : " · préparation locale");
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
  r4Status.textContent = "Version rouverte. Consultez les réserves dans Sources & contexte avant diffusion.";
  uxSavedCard(r4Record);
  r4Controls();
}
async function r4Run(action, writes = false) {
  if (r4Busy || (writes && r4Uncertain)) return;
  r4Busy = true;
  r4Controls();
  try { await action(); if (["loading", "generating", "validating", "saving"].includes(p0Element("status").dataset.state)) p0Element("status").dataset.state = "ready"; }
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
function classroomPreview(target, blocks) {
  const inline = (parent, text) => {
    const pattern = /\*\*([^*]+)\*\*|(?<!\w)\*([^*\n]*\S)\*(?!\w)|`([^`]+)`/g;
    let cursor = 0;
    for (const match of text.matchAll(pattern)) {
      parent.append(document.createTextNode(text.slice(cursor, match.index)));
      const run = document.createElement(match[1] ? "strong" : match[2] ? "em" : "span");
      run.textContent = match[1] || match[2] || match[3]; parent.append(run);
      cursor = match.index + match[0].length;
    }
    parent.append(document.createTextNode(text.slice(cursor)));
  };
  const canonical = value => value.replace(/^#+\s*/, "").trim().toLocaleLowerCase("fr");
  for (let index = 0; index < blocks.length; index++) {
    const block = blocks[index], next = blocks[index + 1]?.text || "";
    if (block.style === "Note" && /^Version exacte : ver:[0-9a-f]{32}$/.test(block.text)) continue;
    if (/^Heading/.test(block.style) && next.split("\n").some(line =>
      /^#+\s/.test(line) && (canonical(line) === canonical(block.text) || canonical(line).startsWith(canonical(block.text) + " —")))) continue;
    if (/^Q\d{2}$/.test(block.text) && next.startsWith("**" + Number(block.text.slice(1)) + ".")) continue;
    const lines = block.text.split("\n");
    for (let lineIndex = 0; lineIndex < lines.length; lineIndex++) {
      let line = lines[lineIndex]; if (!line.trim()) continue;
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        const table = document.createElement("table"); let rowIndex = 0;
        while (lineIndex < lines.length && lines[lineIndex].trim().startsWith("|")) {
          const cells = lines[lineIndex].trim().slice(1, -1).split("|").map(cell => cell.trim());
          if (!cells.every(cell => /^:?-+:?$/.test(cell))) {
            const row = document.createElement("tr");
            for (const text of cells) { const cell = document.createElement(rowIndex === 0 ? "th" : "td"); inline(cell, text); row.append(cell); }
            table.append(row); rowIndex++;
          }
          lineIndex++;
        }
        lineIndex--; target.append(table); continue;
      }
      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      const tag = heading ? "h4" : /^Heading/.test(block.style) ? "h4" : "p";
      line = heading ? heading[2] : line.replace(/^Q(\d{2})(?=\s|$)/, (_, n) => "Question " + Number(n));
      const paragraph = document.createElement(tag); inline(paragraph, line); target.append(paragraph);
    }
  }
}

document.getElementById("r4-preview").addEventListener("click", () => r4Run(async () => {
  const data = await r4Fetch(r4Base() + "/preview/" + document.getElementById("r4-kind").value);
  const target = document.getElementById("r4-preview-content");
  target.replaceChildren();
  appendSearchText(target, "h3", data.title);
  classroomPreview(target, data.blocks);
}));
document.getElementById("r4-download").addEventListener("click", () => r4Run(async () => {
  const kind = document.getElementById("r4-kind").value;
  const data = await r4Fetch(r4Base() + "/word/" + kind, null, true);
  const url = URL.createObjectURL(data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = kind + "-" + (r4Record.record.view.title || "preparation").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9-]/g, "-").replace(/-+/g, "-").slice(0, 80) + ".docx";
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

// P0 companion: all families use the same Application lifecycle and exact versions.
const p0 = {nonce: null, references: [], prepared: null, view: null, teacher: null,
  busy: false, uncertain: false};
const p0Element = id => document.getElementById("p0-" + id);
function p0Controls() {
  p0Element("prepare").disabled = p0.busy || p0.uncertain || !p0.nonce;
  p0Element("generate").disabled = p0.busy || p0.uncertain || !p0.prepared || p0.liveBinding === "NONE" ||
    p0.prepared?.context?.institutional_resolution?.status === "CONTENT_GAP";
  for (const id of ["teacher", "revise", "validate", "save"])
    p0Element(id).disabled = p0.busy || p0.uncertain || !p0.view;
  for (const id of ["open", "modify", "check", "correction", "marking", "export"])
    document.getElementById("card-" + id).disabled = p0.busy || p0.uncertain || !p0.view ||
      (id === "correction" && !p0.view.questions.length && !p0.view.course_chapter) ||
      (id === "marking" && p0.view.pedagogical_context.resource_type !== "ASSESSMENT");
}
async function p0Fetch(path, body = null) {
  const options = {method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
    redirect: "error", headers: {"X-Local-Intent": "conversation-v1"}};
  if (body) {
    options.headers["Content-Type"] = "application/json; charset=utf-8";
    options.headers["X-R2-Nonce"] = p0.nonce;
    options.body = JSON.stringify(body);
  }
  return localBoundedRequest(path, options, async response => {
  const envelope = await response.json();
  if (!response.ok || envelope?.meta?.contract_id !== "R6-P0-HTTP-LOCAL-1.0") {
    const error = new Error(envelope?.error?.code || "P0_REFUSED");
    error.confirmedRefusal = envelope?.meta?.contract_id === "R6-P0-HTTP-LOCAL-1.0" &&
      envelope?.error?.code !== "P0_OUTCOME_UNKNOWN";
    throw error;
  }
  return envelope.data;
  });
}
async function p0Run(action, mutation = false, state = "loading") {
  if (p0.busy || (mutation && p0.uncertain)) return;
  p0.busy = true; p0Controls();
  p0Element("status").dataset.state = state;
  p0Element("status").textContent = "Action en cours…";
  try { await action(); if (["loading", "generating", "validating", "saving"].includes(p0Element("status").dataset.state)) p0Element("status").dataset.state = "ready"; }
  catch (error) {
    if (mutation && !error.confirmedRefusal) p0.uncertain = true;
    p0Element("status").dataset.state = "error";
    p0Element("status").textContent = "Action non confirmée : " + error.message +
      (p0.uncertain ? ". Aucun renvoi automatique ; vérifiez la version avant de reprendre." :
        error.confirmedRefusal ? ". Refus confirmé ; corrigez la demande avant une nouvelle action explicite." : ". Réessayez la consultation explicitement.");
  } finally { p0.busy = false; p0Controls(); uxMessage("assistant", p0Element("status").textContent); }
}
const p0Command = () => crypto.randomUUID().replaceAll("-", "");
function p0Context() {
  const family = p0Element("family").value;
  const context = {contract_id: "R6-P0-CONTEXT-1.0",
    resource_type: ["OPEN_QUESTIONS", "QCM", "QUIZ"].includes(family) ? "QUESTION_SET" : family,
    question_mode: ["OPEN_QUESTIONS", "QCM", "QUIZ"].includes(family) ? family : null,
    level: p0Element("level").value, discipline: p0Element("discipline").value.trim(),
    topics: p0Element("topics").value.split("\n").map(t => t.trim()).filter(Boolean),
    objectives: p0Element("objectives").value.split("\n").map(t => t.trim()).filter(Boolean),
    difficulty: p0Element("difficulty").value, language: "fr",
    duration_minutes: family === "ASSESSMENT" ? Number(p0Element("duration").value) : null,
    total_points: family === "ASSESSMENT" ? Number(p0Element("points").value) : null};
  if (context.level.endsWith("STMG")) {
    const frame = p0InstitutionalFrame();
    const question = frame?.questions.find(q => q.question_ref === p0Element("program-question").value);
    if (!frame || !question || !p0Element("depth").value)
      throw Object.assign(new Error("P0_INSTITUTIONAL_CONTEXT_REQUIRED"), {confirmedRefusal: true});
    context.contract_id = "P0-CONTEXT-2.0";
    context.discipline = frame.label;
    context.institutional = {contract_id: "STMG-INSTITUTIONAL-CONTEXT-1.0", frame: frame.frame,
      education_level: frame.education_level, series: "STMG", teaching_subject: frame.teaching_subject,
      program_ref: frame.program_ref, program_version: frame.program_version,
      program_component: frame.program_component, specific_track: frame.specific_track,
      theme_ref: question.theme_ref ?? null, question_ref: question.question_ref,
      capacity_refs: [...p0Element("capacities").selectedOptions].map(o => o.value),
      notion_refs: [...p0Element("program-notions").selectedOptions].map(o => o.value), depth: p0Element("depth").value};
    context.institutional_resolution = null;
    context.local_progression = {chapter: p0Element("local-chapter").value.trim() || null,
      sequence: p0Element("local-sequence").value.trim() || null, week: p0Element("local-week").value.trim() || null};
  }
  return context;
}
function p0InstitutionalFrame() {
  return (p0.institutionalCatalog?.frames || []).find(f => f.program_version === p0Element("frame").value && f.level === p0Element("level").value);
}
function p0InstitutionalOptions() {
  const stmg = p0Element("level").value.endsWith("STMG");
  p0Element("institutional").hidden = !stmg;
  p0Element("discipline").readOnly = stmg;
  for (const id of ["frame", "program-question", "program-notions", "depth"]) p0Element(id).required = stmg;
  const select = p0Element("frame"); select.replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Choisir l’enseignement exact"; select.append(empty);
  for (const frame of p0.institutionalCatalog?.frames || []) {
    if (frame.level !== p0Element("level").value) continue;
    const option = document.createElement("option"); option.value = frame.program_version;
    option.textContent = frame.label + " · " + frame.version_label; select.append(option);
  }
  p0InstitutionalQuestionOptions();
  const notions = p0Element("program-notions"); notions.replaceChildren();
  for (const notion of p0.institutionalCatalog?.notions || []) {
    const option = document.createElement("option"); option.value = notion.notion_ref; option.textContent = notion.label; notions.append(option);
  }
}
function p0InstitutionalQuestionOptions() {
  const frame = p0InstitutionalFrame();
  if (p0Element("level").value.endsWith("STMG")) p0Element("discipline").value = frame?.label || "";
  const select = p0Element("program-question"); select.replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Choisir la question"; select.append(empty);
  for (const question of frame?.questions || []) {
    const option = document.createElement("option"); option.value = question.question_ref;
    option.textContent = question.label + (question.theme_ref ? "" : " · thème à renseigner"); select.append(option);
  }
  p0InstitutionalCapacityOptions();
}
function p0InstitutionalCapacityOptions() {
  const frame = p0InstitutionalFrame();
  const question = frame?.questions.find(q => q.question_ref === p0Element("program-question").value);
  const select = p0Element("capacities"); select.replaceChildren();
  for (const capacity of frame?.capacities || []) {
    if (capacity.question_ref !== p0Element("program-question").value) continue;
    const option = document.createElement("option"); option.value = capacity.capacity_ref; option.textContent = capacity.label; select.append(option);
  }
  p0Element("program-status").textContent = (frame?.authority === "UNATTESTED" ?
    "Snapshot local : provenance officielle à compléter. Aucune génération tant que les rattachements ne sont pas admis." :
    "Les capacités et rattachements seront contrôlés dans ce programme exact.") +
    (question && !question.theme_ref ? " Thème non renseigné dans la source : la question est sélectionnable, mais la génération reste bloquée." : "");
}
p0Element("level").addEventListener("change", p0InstitutionalOptions);
p0Element("frame").addEventListener("change", p0InstitutionalQuestionOptions);
p0Element("program-question").addEventListener("change", p0InstitutionalCapacityOptions);
p0Element("family").addEventListener("change", () => {
  const assessment = p0Element("family").value === "ASSESSMENT";
  p0Element("assessment").hidden = !assessment;
  for (const id of ["duration", "points"]) p0Element(id).required = assessment;
});
function p0Invalidate() {
  p0.prepared = null; p0Controls();
}
p0Element("form").addEventListener("input", p0Invalidate);
p0Element("form").addEventListener("change", p0Invalidate);
p0Element("form").addEventListener("submit", event => {
  event.preventDefault();
  p0Run(async () => {
    const query = p0Element("search-query").value.trim();
    const notion = p0Element("notion-id").value.trim();
    const passage = p0Element("search-passage").value.trim();
    const selected = p0.references[Number(p0Element("reference").value)];
    if (Boolean(query || notion) !== Boolean(passage) || (query && notion))
      throw Object.assign(new Error("P0_REFERENCE_INCOMPLETE"), {confirmedRefusal: true});
    if ((!(query || notion) || !passage) && (!selected || p0Element("reference").value === ""))
      throw Object.assign(new Error("P0_REFERENCE_REQUIRED"), {confirmedRefusal: true});
    const reference = notion && passage ? {notion_id: notion, passage_ref: passage} : query && passage ? {query, passage_ref: passage} :
      {resource_ref: selected.resource_ref, resource_version_ref: selected.resource_version_ref};
    p0.prepared = await p0Fetch("/api/v2/p0/prepare", {command_id: p0Command(), context: p0Context(), reference});
    p0Element("preparation").replaceChildren();
    appendSearchText(p0Element("preparation"), "p", "Contexte et référence confirmés. Relisez ce choix avant de générer.");
    const sourceDetails = document.createElement("details"); sourceDetails.className = "secondary";
    appendSearchText(sourceDetails, "summary", "Contexte exact, sources et provenance");
    appendSearchText(sourceDetails, "pre", JSON.stringify({context: p0.prepared.context,
      references: p0.prepared.references}, null, 2));
    p0Element("preparation").append(sourceDetails);
    uxPreparation(p0.prepared);
    p0Element("status").textContent = p0.prepared.context.institutional_resolution?.status === "CONTENT_GAP" ?
      "Préparation enregistrée avec lacunes institutionnelles. Génération bloquée ; consultez Sources & contexte." :
      "Préparation prête. Autorisation de génération requise ; aucun appel fournisseur effectué.";
  }, true);
});
function p0Field(parent, id, label, value, multiline = true) {
  const text = document.createElement("label"); text.htmlFor = id; text.textContent = label;
  const input = document.createElement(multiline ? "textarea" : "input");
  input.id = id; input.value = value; if (multiline) input.rows = 3;
  parent.append(text, input); return input;
}
function p0Render(view) {
  p0.view = view; p0.teacher = null;
  const region = p0Element("review"); region.replaceChildren();
  p0Element("teacher-content").replaceChildren();
  appendSearchText(region, "p", "Préparation à relire avant usage pédagogique.");
  uxProductionCard(view);
  p0Field(region, "p0-edit-title", "Titre", view.title, false);
  view.sections.forEach((s, i) => {
    p0Field(region, "p0-edit-heading-" + i, "Titre de section " + (i + 1), s.heading, false);
    p0Field(region, "p0-edit-section-" + i, "Texte de section " + (i + 1), s.text);
  });
  view.questions.forEach((q, i) => {
    p0Field(region, "p0-edit-question-" + i, "Question " + (i + 1), q.prompt);
    if (q.options.length) p0Field(region, "p0-edit-options-" + i, "Options — une par ligne", q.options.join("\n"));
  });
}
function p0Identity() {
  return {production_ref: p0.view.production_ref, version_ref: p0.view.version_ref,
    bundle_sha256: p0.view.bundle_sha256};
}
p0Element("generate").addEventListener("click", () => p0Run(async () => {
  const result = await p0Fetch("/api/v2/p0/generate", {command_id: p0Command(),
    preparation_ref: p0.prepared.preparation_ref, preparation_sha256: p0.prepared.preparation_sha256});
  if (result.state === "CANDIDATE") {
    uxQuality(result.agentic?.quality);
    p0Render(result.view); p0.prepared = null;
    p0Element("status").textContent = "Candidate reçue. Relisez et modifiez la version exacte ; aucune promotion effectuée.";
  } else { p0Element("status").dataset.state = "unavailable";
    p0Element("status").textContent = "Génération indisponible : autorisation requise. Aucun transport fournisseur n’est lié à cette composition hors ligne."; }
}, true, "generating"));
p0Element("teacher").addEventListener("click", () => p0Run(async () => {
  p0.teacher = await p0Fetch("/api/v2/p0/versions/" + p0.view.production_ref + "/" + p0.view.version_ref + "/teacher");
  const region = p0Element("teacher-content"); region.replaceChildren();
  appendSearchText(region, "h3", "Compagnons professeur — consultation séparée");
  p0.teacher.corrections.forEach((c, i) => {
    p0Field(region, "p0-edit-answer-" + i, "Réponse " + c.question_id, c.expected_answer);
    p0Field(region, "p0-edit-rationale-" + i, "Explication " + c.question_id, c.rationale);
  });
  p0.teacher.marking.forEach((m, i) => {
    p0Field(region, "p0-edit-points-" + i, "Points " + m.question_id, m.points, false);
    p0Field(region, "p0-edit-criteria-" + i, "Critères — un par ligne", m.criteria.join("\n"));
  });
}));
p0Element("revise").addEventListener("click", () => p0Run(async () => {
  const edits = {title: document.getElementById("p0-edit-title").value,
    sections: p0.view.sections.map((s, i) => ({...s, heading: document.getElementById("p0-edit-heading-" + i).value,
      text: document.getElementById("p0-edit-section-" + i).value})),
    questions: p0.view.questions.map((q, i) => ({...q, prompt: document.getElementById("p0-edit-question-" + i).value,
      options: q.options.length ? document.getElementById("p0-edit-options-" + i).value.split("\n") : []}))};
  if (p0.teacher) {
    edits.corrections = p0.teacher.corrections.map((c, i) => ({...c,
      expected_answer: document.getElementById("p0-edit-answer-" + i).value,
      rationale: document.getElementById("p0-edit-rationale-" + i).value}));
    edits.marking = p0.teacher.marking.map((m, i) => ({...m, points: document.getElementById("p0-edit-points-" + i).value,
      criteria: document.getElementById("p0-edit-criteria-" + i).value.split("\n")}));
  }
  const result = await p0Fetch("/api/v2/p0/revise", {command_id: p0Command(), ...p0Identity(), edits});
  p0Render(result.view); p0Element("status").textContent = "Nouvelle version conservée ; la version parente est inchangée.";
}, true));
p0Element("validate").addEventListener("click", () => p0Run(async () => {
  const report = await p0Fetch("/api/v2/p0/validate", {command_id: p0Command(), ...p0Identity()});
  uxQuality(report.quality);
  p0Element("status").textContent = "Vérification structurelle : " + report.status + ". Aucune validation pédagogique ni promotion.";
}, true, "validating"));
async function p0SaveVersion() {
  const refs = {production_ref: p0.view.production_ref, version_ref: p0.view.version_ref};
  await r4Fetch("/api/v2/conversation/saved", refs);
  await r4Refresh(); r4Versions.value = refs.production_ref + "/" + refs.version_ref;
  await r4Open(); p0Element("status").textContent = "Version sauvegardée et rouverte. Exports disponibles dans l’espace de conservation.";
}
p0Element("save").addEventListener("click", () => p0Run(p0SaveVersion, true, "saving"));
async function p0Connect() {
  const metadata = await p0Fetch("/api/v2/p0");
  p0.nonce = metadata.transport_nonce; p0.references = metadata.references;
  p0.institutionalCatalog = metadata.institutional_catalog;
  p0InstitutionalOptions();
  p0.liveBinding = metadata.live_binding;
  p0Element("generate").textContent = metadata.live_binding === "NONE" ? "Génération indisponible dans cette composition" : "Demander la génération autorisée";
  p0Element("reference").replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Choisir une référence";
  p0Element("reference").append(empty);
  p0.references.forEach((ref, i) => {
    const option = document.createElement("option"); option.value = String(i);
    option.textContent = ref.title;
    p0Element("reference").append(option);
  });
  p0Element("status").textContent = "Contexte prêt à renseigner. Aucune génération autorisée.";
}
p0Element("connect").addEventListener("click", () => p0Run(p0Connect));
p0Run(p0Connect);

// Conversational shell: proposals are deterministic and explicitly confirmed.
// Business versions are saved through Application, never in browser storage.
const uxRequests = [];
const uxNames = {COURSE: "Cours", EXERCISE: "Exercice", OPEN_QUESTIONS: "Questions ouvertes", QCM: "QCM", QUIZ: "Quiz", ASSESSMENT: "Évaluation",
  FIRST_STMG: "Première STMG", FINAL_STMG: "Terminale STMG", BTS_CG_YEAR_1: "BTS CG première année", BTS_CG_YEAR_2: "BTS CG deuxième année"};
function uxShow(name) {
  document.querySelectorAll("[data-panel]").forEach(panel => { panel.hidden = panel.dataset.panel !== name; });
  document.querySelectorAll("[data-view]").forEach(button => { button.setAttribute("aria-current", button.dataset.view === name ? "page" : "false"); });
  document.getElementById("workspace-title").textContent = {prepare: "Nouvelle préparation", conversations: "Conversations", productions: "Productions", library: "Bibliothèque", settings: "Réglages"}[name];
}
function uxMessage(role, text) {
  const messages = document.getElementById("preparation-messages");
  if (messages.lastElementChild?.textContent === text) return;
  appendSearchText(messages, "li", text, "message-" + role);
  while (messages.children.length > 64) messages.firstElementChild.remove();
}
function proposePreparation(text) {
  const normalized = text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const families = [["COURSE", /\bcours\b/], ["EXERCISE", /\bexercice[s]?\b/], ["OPEN_QUESTIONS", /\bquestions? ouvertes?\b/],
    ["QCM", /\bqcm\b/], ["QUIZ", /\bquiz\b/], ["ASSESSMENT", /\b(evaluation|controle|epreuve)\b/]];
  const levels = [["FIRST_STMG", /\b(premiere|1re|1ere) stmg\b/], ["FINAL_STMG", /\b(terminale|tle) stmg\b/],
    ["BTS_CG_YEAR_1", /\bbts cg (?:1|premiere annee|annee 1)\b/], ["BTS_CG_YEAR_2", /\bbts cg (?:2|deuxieme annee|seconde annee|annee 2)\b/]];
  const foundFamilies = families.filter(([, pattern]) => pattern.test(normalized)).map(([name]) => name);
  const foundLevels = levels.filter(([, pattern]) => pattern.test(normalized)).map(([name]) => name);
  const topic = text.match(/\bsur\s+(.+?)(?:[.!?]|,\s*(?:durée|noté|pour)|$)/i)?.[1]?.trim() || "";
  const minutes = normalized.match(/\b(\d{1,3})\s*(?:minutes?|min)\b/);
  const hours = normalized.match(/\b(\d)\s*(?:heures?|h)\b/);
  const points = normalized.match(/(?:note\s*)?sur\s+(\d{1,3})\b/);
  return {family: foundFamilies.length === 1 ? foundFamilies[0] : "", level: foundLevels.length === 1 ? foundLevels[0] : "", topic,
    difficulty: /\b(approfondi|avance|difficile)\b/.test(normalized) ? "ADVANCED" : /\b(initiation|debutant)\b/.test(normalized) ? "INTRODUCTORY" : "STANDARD",
    duration: minutes ? Number(minutes[1]) : hours ? Number(hours[1]) * 60 : null, points: points ? Number(points[1]) : null,
    objective: text.length <= 500 ? text : "",
    ambiguities: [...(foundFamilies.length === 1 ? [] : ["type de production"]), ...(foundLevels.length === 1 ? [] : ["niveau exact"]),
      ...(topic ? [] : ["notions"]), ...(text.length <= 500 ? [] : ["objectif synthétique (500 caractères maximum)"])]};
}
function uxContext(context) {
  const region = document.getElementById("drawer-context"); region.replaceChildren();
  appendSearchText(region, "p", (uxNames[context.question_mode || context.resource_type] || "Type à préciser") + " · " + (uxNames[context.level] || "Niveau à préciser"));
  appendSearchText(region, "p", context.discipline || "Discipline à préciser");
  if (context.institutional) {
    const selected = context.institutional, resolved = context.institutional_resolution;
    const level = selected.education_level === "PREMIERE" ? "Première STMG" : "Terminale STMG";
    appendSearchText(region, "p", "Niveau : " + level);
    appendSearchText(region, "p", "Enseignement : " + context.discipline.split(" — ")[0]);
    if (selected.program_component === "COMMON") appendSearchText(region, "p", "Partie : Enseignement commun");
    if (selected.program_component === "SPECIFIC") appendSearchText(region, "p", "Enseignement spécifique : " + context.discipline.split(" — ").slice(1).join(" — "));
    appendSearchText(region, "p", "Programme : " + context.discipline + " — " + level + " · " + (resolved?.version_label || "version sélectionnée à vérifier"));
    appendSearchText(region, "p", (selected.theme_ref ? "Thème " + selected.theme_ref.replace("theme:", "") : "Thème non renseigné") + " · " + (resolved?.question?.official_label || "question sélectionnée à vérifier"));
    appendSearchText(region, "p", "Capacités : " + ((resolved?.capacities || []).map(c => c.label).join(" · ") || "rattachements à compléter"));
    appendSearchText(region, "p", "Notions : " + ((resolved?.notions || []).map(n => n.label).join(" · ") || "sélection à vérifier") + " · " +
      ({DISCOVERY:"Découverte", APPLICATION:"Application", ANALYSIS:"Analyse"}[selected.depth] || "profondeur à préciser"));
    if (resolved?.gaps?.length) appendSearchText(region, "p", "Lacunes institutionnelles : provenance, capacités ou liens encore non admis. Génération bloquée.");
    if (context.local_progression) appendSearchText(region, "p", "Progression locale : " + Object.values(context.local_progression).filter(Boolean).join(" · "));
  }
  appendSearchText(region, "p", (context.topics || []).join(" · "));
  if (context.duration_minutes) appendSearchText(region, "p", context.duration_minutes + " minutes · /" + context.total_points);
}
function uxQuality(quality) {
  if (!quality) return;
  const labels = {SOURCES_OK: "Identité des sources contrôlée", SOURCES_INSUFFICISANTES: "Sources insuffisantes", CALCULS_VERIFIES: "Calculs vérifiés", ECHEC: "Preuve indépendante des calculs manquante", NON_APPLICABLE: "Calculs non requis par les notions déclarées", CONSIGNE_COUVERTE: "Couverture examinée", PARTIELLE: "Couverture à examiner", REVUE_OK: "Revue technique sans réserve", RESERVE: "Revue pédagogique en attente ou avec réserves", HUMAN_REVIEW_REQUIRED: "Relecture enseignante nécessaire"};
  const region = document.getElementById("drawer-quality"); region.replaceChildren();
  for (const key of ["sources", "calculations", "instruction", "review", "human_review"]) appendSearchText(region, "p", labels[quality[key]] || "Non vérifié");
}
function uxPreparation(prepared) {
  uxContext(prepared.context); uxQuality(prepared.agentic?.quality);
  const region = document.getElementById("drawer-sources"); region.replaceChildren();
  const passages = prepared.agentic?.evidence_pack?.passages || [];
  for (const passage of passages) appendSearchText(region, "p", passage.text);
  if (!passages.length) appendSearchText(region, "p", prepared.references.length + " référence(s) sélectionnée(s).");
  document.getElementById("drawer-identities").textContent = JSON.stringify({preparation_ref: prepared.preparation_ref,
    preparation_sha256: prepared.preparation_sha256, references: prepared.references, plan: prepared.agentic?.plan}, null, 2);
}
function uxProductionCard(view) {
  const context = view.pedagogical_context;
  document.getElementById("production-card").hidden = false;
  document.getElementById("production-card-title").textContent = view.title;
  document.getElementById("production-card-context").textContent = (uxNames[context.question_mode || context.resource_type] || "Préparation") + " · " + uxNames[context.level] +
    (context.duration_minutes ? " · " + context.duration_minutes + " minutes · /" + context.total_points : "");
  const preview = document.getElementById("production-card-preview"); preview.replaceChildren();
  const teacherPreview = document.getElementById("production-card-teacher-preview");
  teacherPreview.replaceChildren(); teacherPreview.hidden = true;
  classroomPreview(preview, [...view.sections.flatMap(section => [{style: "Heading1", text: section.heading}, {style: "Normal", text: section.text}]),
    ...view.questions.flatMap((question, i) => [{style: "Heading2", text: "Question " + (i + 1)}, {style: "Normal", text: question.prompt},
      ...question.options.map(option => ({style: "Normal", text: option}))])]);
  uxContext(context);
  document.getElementById("drawer-identities").textContent = JSON.stringify({production_ref: view.production_ref, version_ref: view.version_ref, bundle_sha256: view.bundle_sha256, references: view.references}, null, 2);
  document.getElementById("production-edit-panel").open = false;
}
async function uxTeacherCard(kind) {
  await p0Run(async () => {
    const teacher = await p0Fetch("/api/v2/p0/versions/" + p0.view.production_ref + "/" + p0.view.version_ref + "/teacher");
    const region = document.getElementById("production-card-teacher-preview");
    region.replaceChildren(); region.hidden = false;
    appendSearchText(region, "h3", kind === "correction" ? "Correction — document professeur séparé" : "Barème — document professeur séparé");
    if (kind === "correction" && teacher.course_chapter) teacher.course_chapter.teacher_answers.forEach((c, i) => {
      appendSearchText(region, "h4", "Question " + (i + 1));
      appendSearchText(region, "p", c.expected_answer); appendSearchText(region, "p", c.rationale);
      appendSearchText(region, "p", "Point de vigilance : " + c.vigilance);
      appendSearchText(region, "p", "Remédiation : " + c.remediation);
    });
    else if (kind === "correction") teacher.corrections.forEach((c, i) => {
      appendSearchText(region, "h4", "Question " + (i + 1));
      appendSearchText(region, "p", c.expected_answer); appendSearchText(region, "p", c.rationale);
    });
    else teacher.marking.forEach((m, i) => {
      appendSearchText(region, "h4", "Question " + (i + 1) + " — " + m.points + " points");
      m.criteria.forEach(criterion => appendSearchText(region, "p", criterion));
    });
    p0Element("status").textContent = "Document professeur consulté séparément. Le sujet élève est inchangé.";
  });
}
function uxSavedCard(saved) {
  const view = saved.record.view;
  uxContext(view.context || view.pedagogical_context || {});
  document.getElementById("drawer-identities").textContent = JSON.stringify({production_ref: view.production_ref, version_ref: view.version_ref,
    record_sha256: saved.record_sha256, provenance: saved.record.provenance, reviews: saved.record.reviews, validations: saved.record.validations}, null, 2);
  document.getElementById("drawer-sources").textContent = "Provenance de la version conservée : consultable dans Traçabilité exacte. Aucune autorité officielle restaurée.";
  document.getElementById("drawer-quality").textContent = "Relecture nécessaire. Les rapports conservés couvrent uniquement leur version exacte.";
}
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => uxShow(button.dataset.view)));
document.getElementById("new-preparation").addEventListener("click", () => {
  uxShow("prepare"); document.getElementById("preparation-prompt").value = ""; document.getElementById("preparation-prompt").focus();
});
document.getElementById("sources-toggle").addEventListener("click", () => {
  const drawer = document.getElementById("sources-drawer"); drawer.hidden = !drawer.hidden;
  document.body.classList.toggle("drawer-closed", drawer.hidden);
  document.getElementById("sources-toggle").setAttribute("aria-expanded", String(!drawer.hidden));
});
document.querySelectorAll("[data-family]").forEach(button => button.addEventListener("click", () => {
  document.getElementById("preparation-prompt").value = "Prépare " + uxNames[button.dataset.family].toLocaleLowerCase("fr") + " ";
  document.getElementById("preparation-prompt").focus();
}));
document.getElementById("preparation-composer").addEventListener("submit", event => {
  event.preventDefault();
  if (p0.busy || p0.uncertain) { uxMessage("assistant", "Terminez ou vérifiez l’action en attente avant une nouvelle préparation."); return; }
  const text = document.getElementById("preparation-prompt").value.trim(); if (!text) return;
  const proposed = proposePreparation(text);
  uxMessage("user", text); uxRequests.push(text); if (uxRequests.length > 32) uxRequests.shift();
  for (const id of ["recent-preparations", "session-conversations"]) {
    const region = document.getElementById(id); region.replaceChildren();
    [...uxRequests].reverse().forEach(request => { const item = document.createElement("li"), button = document.createElement("button");
      button.type = "button"; button.textContent = request; button.addEventListener("click", () => { uxShow("prepare"); document.getElementById("preparation-prompt").value = request; }); item.append(button); region.append(item); });
  }
  // Replace the proposed context, but retain the explicitly selected source.
  p0Element("family").value = proposed.family; p0Element("level").value = proposed.level;
  p0Element("difficulty").value = proposed.difficulty; p0Element("topics").value = proposed.topic;
  p0Element("objectives").value = proposed.objective;
  p0Element("discipline").value = proposed.level.includes("BTS") ? "Comptabilité et gestion" : "";
  p0InstitutionalOptions();
  p0Element("duration").value = proposed.duration || ""; p0Element("points").value = proposed.points || "";
  p0Element("family").dispatchEvent(new Event("change")); p0Invalidate();
  document.getElementById("preparation-parameters").open = true;
  if (proposed.level.includes("STMG")) uxMessage("assistant", "Choisissez l’enseignement exact et sa question : Management et SGN sont distincts ; en terminale, précisez le commun ou l’enseignement spécifique.");
  else uxContext(p0Context());
  uxMessage("assistant", proposed.ambiguities.length ? "À préciser pour préparer : " + proposed.ambiguities.join(", ") + ". Complétez le contexte puis sélectionnez une source." :
    "Le contexte proposé est prêt à confirmer. Relisez les paramètres, puis sélectionnez une référence ou un passage de la Bibliothèque.");
  if (proposed.duration && proposed.family !== "ASSESSMENT") uxMessage("assistant", "La durée est actuellement enregistrable pour les évaluations uniquement. Votre demande reste visible ; aucune durée ne sera ajoutée au contrat de cette production.");
  document.getElementById("preparation-prompt").value = "";
});
document.getElementById("card-open").addEventListener("click", () => {
  document.getElementById("production-card-teacher-preview").hidden = true;
  document.getElementById("production-card-preview").hidden = false;
  document.getElementById("production-card-preview").scrollIntoView({behavior: "smooth"});
});
document.getElementById("card-modify").addEventListener("click", () => { document.getElementById("production-edit-panel").open = true; document.getElementById("p0-edit-title").focus(); });
document.getElementById("card-check").addEventListener("click", () => p0Element("validate").click());
document.getElementById("card-correction").addEventListener("click", () => uxTeacherCard("correction"));
document.getElementById("card-marking").addEventListener("click", () => uxTeacherCard("marking"));
document.getElementById("card-export").addEventListener("click", () => p0Run(async () => {
  await p0SaveVersion(); uxShow("productions");
}, true, "saving"));
if (window.matchMedia("(max-width:1180px)").matches) document.getElementById("sources-toggle").click();
