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
      if (item.source_status) {
        const source = item.source_status;
        if (source.contract_id !== "SEARCH-SOURCE-STATUS-1.0" ||
            [source.identity_status, source.lifecycle_status, source.validation_status].some(value => typeof value !== "string" || !/^[A-Z][A-Z0-9_]{0,39}$/.test(value)))
          throw new Error("INVALID_PUBLIC_SOURCE_STATUS");
        appendSearchText(row, "p", "Identité : " + source.identity_status + " · Cycle de vie : " +
          source.lifecycle_status + " · Validation : " + source.validation_status +
          (source.status_basis === "EXACT_VERSION_REQUIRED" ? " · Version exacte à consulter." : "") +
          " Ces statuts n'attestent pas l'autorité officielle.", "provenance");
      }
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
        const notions = [...p0Element("program-notions").selectedOptions].map(option => option.value);
        p0Element("search-query").value = notions.length === 1 ? "" : searchInput.value;
        p0Element("notion-id").value = notions.length === 1 ? notions[0] : "";
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

async function localBoundedRequest(path, options, consume, timeoutMs = 10000) {
  if (![10000, 60000, 150000].includes(timeoutMs)) throw new Error("LOCAL_REQUEST_TIMEOUT_POLICY");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await consume(await fetch(path, {...options, signal: controller.signal}));
  } catch (error) {
    if (controller.signal.aborted) error.localTimedOut = true;
    throw error;
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
let r4ResumePending = false;
let r4Uncertain = false;
let r4SavedVersions = [];
const r4Status = document.getElementById("r4-status");
const r4Versions = document.getElementById("r4-version");
function r4Base() {
  const view = r4Record?.record?.view;
  if (!view) throw new Error("R4_NOT_OPEN");
  return "/api/v2/productions/" + view.production_ref + "/versions/" + view.version_ref;
}
function r4AvailableKinds(record) {
  const bundle = record?.bundle, context = bundle?.context;
  if (!context) return ["student", "correction", "marking"];
  if (context.resource_type === "ASSESSMENT") return ["student", "correction", "marking"];
  if (context.resource_type === "COURSE") return bundle.course_chapter ? ["student", "correction"] : ["student"];
  return ["student", "correction"];
}
function r4Controls() {
  const kinds = r4AvailableKinds(r4Record?.record);
  const selector = document.getElementById("r4-kind");
  for (const option of selector.options) option.disabled = !kinds.includes(option.value);
  if (!kinds.includes(selector.value)) selector.value = "student";
  document.getElementById("r4-resume").disabled = r4Busy || r4ResumePending || !r4Record ||
    r4Record.record.origin !== "LOCAL_APPLICATION" || !r4Record.record.view.bundle_sha256;
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
  if (!response.ok && response.status === 409 && envelope?.meta?.contract_id === "P0-MEDIA-EXPORT-REFUSAL-1.0") {
    const messages = {
      PRODUCTION_MEDIA_REQUIRED_MISSING: "Un visuel obligatoire manque. Complétez le plan média avant l’export.",
      PRODUCTION_MEDIA_EXPORT_ANCHOR_UNAVAILABLE: "Le document ne contient plus le point d’insertion du visuel. Corrigez son rattachement avant l’export.",
      PRODUCTION_WORD_ANCHOR_AMBIGUOUS: "Plusieurs titres correspondent au visuel. Clarifiez son point d’insertion avant l’export."
    };
    if (messages[envelope?.error?.code]) throw new Error(messages[envelope.error.code]);
  }
  if (!response.ok || envelope?.meta?.contract_id !== "SAVE-REOPEN-WORD-HTTP-LOCAL-1.0")
    throw new Error(envelope?.error?.code || "R4_REFUSED");
  return envelope.data;
  }, 60000);
}
async function r4Refresh() {
  const data = await r4Fetch("/api/v2/conversation/saved");
  r4Nonce = data.transport_nonce;
  const selected = r4Versions.value;
  r4Versions.replaceChildren();
  for (const version of data.versions) {
    const option = document.createElement("option");
    option.value = version.production_ref + "/" + version.version_ref;
    option.textContent = (version.title || "Production conservée") + " · " + version.version_ref.slice(-8) +
      (version.origin === "IMPORTED_DOCUMENTARY" ? " · lecture seule" : " · préparation locale");
    option.dataset.recordSha256 = version.record_sha256;
    option.selected = option.value === selected;
    r4Versions.append(option);
  }
  r4Status.textContent = data.versions.length + " version(s) conservée(s) sur disque. Aucune autorité restaurée.";
  r4SavedVersions = data.versions;
  uxHomeVersions(data.versions);
  r4Controls();
}
async function r4Open() {
  if (!uxDraftConfirm()) return;
  const refs = r4Versions.value.split("/");
  if (refs.length !== 2 || !/^prod:[0-9a-f]{32}$/.test(refs[0]) || !/^ver:[0-9a-f]{32}$/.test(refs[1]))
    throw new Error("R4_INVALID_SELECTION");
  const selected = r4Versions.value;
  const expectedHash = r4Versions.selectedOptions[0]?.dataset.recordSha256;
  const opened = await r4Fetch("/api/v2/productions/" + refs[0] + "/versions/" + refs[1] + "/saved");
  if (r4Versions.value !== selected) throw new Error("R4_SELECTION_CHANGED");
  if (opened.record?.view?.production_ref !== refs[0] || opened.record?.view?.version_ref !== refs[1] ||
      (expectedHash && opened.record_sha256 !== expectedHash)) throw new Error("R4_SAVED_IDENTITY_CHANGED");
  r4Record = opened;
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
  uxHomeVersions(r4SavedVersions);
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
function classroomPreview(target, blocks, assets = []) {
  const insertions = new Map();
  for (const asset of assets) {
    const matches = blocks.map((block, index) => ({block,index})).filter(({block}) =>
      /^Heading/.test(block.style) && (asset.anchor_heading ? block.text === asset.anchor_heading : block.anchor_ref === asset.section_ref));
    if (matches.length !== 1) throw new Error("P0_MEDIA_PREVIEW_ANCHOR_UNAVAILABLE");
    let index = matches[0].index;
    const following = blocks[index + 1]?.text || "";
    if (following.split("\n").some(line => /^#+\s/.test(line) &&
        line.replace(/^#+\s*/, "").trim().toLocaleLowerCase("fr").startsWith(
          blocks[index].text.trim().toLocaleLowerCase("fr")))) index++;
    if (asset.preferred_position === "AFTER_DOCUMENT" || asset.preferred_position === "AFTER_CONTEXT") {
      while (index + 1 < blocks.length && !/^Heading/.test(blocks[index + 1].style)) index++;
    }
    insertions.set(index, [...(insertions.get(index) || []), asset]);
  }
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
    if (block.table) {
      const table = document.createElement("table");
      for (const [rowIndex, cells] of [block.table.columns, ...block.table.rows].entries()) {
        const row = document.createElement("tr");
        for (const text of cells) {const cell=document.createElement(rowIndex === 0 ? "th" : "td");inline(cell,text);row.append(cell);}
        table.append(row);
      }
      target.append(table);
      if (insertions.has(index)) uxMediaAssets(target, insertions.get(index));
      continue;
    }
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
    if (insertions.has(index)) uxMediaAssets(target, insertions.get(index));
  }
}

document.getElementById("r4-preview").addEventListener("click", () => r4Run(async () => {
  const saved = r4Record, kind = document.getElementById("r4-kind").value;
  const data = await r4Fetch(r4Base() + "/preview/" + kind);
  if (r4Record !== saved || document.getElementById("r4-kind").value !== kind || data.kind !== kind)
    throw new Error("R4_PREVIEW_SELECTION_CHANGED");
  const target = document.getElementById("r4-preview-content");
  target.replaceChildren();
  appendSearchText(target, "h3", data.title);
  classroomPreview(target, data.blocks, data.media_assets || data.course_chapter?.media_assets || []);
}));
document.getElementById("r4-download").addEventListener("click", () => r4Run(async () => {
  const saved = r4Record;
  const kind = document.getElementById("r4-kind").value;
  const data = await r4Fetch(r4Base() + "/word/" + kind, null, true);
  if (r4Record !== saved || document.getElementById("r4-kind").value !== kind)
    throw new Error("R4_DOWNLOAD_SELECTION_CHANGED");
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
const p0 = {nonce: null, references: [], prepared: null, view: null, teacher: null, consent: null,
  busy: false, uncertain: false, contextRevision: 0, editInputs: [], connected: false,
  liveBinding: "NONE", normalConsentBinding: "NONE", mediaBinding: "NONE",
  localReferenceContextBinding: "NONE", localReferenceContexts: []};
let p0ConnectionPromise = null;
const p0Element = id => document.getElementById("p0-" + id);
function p0Controls() {
  for (const input of p0.editInputs || []) input.disabled = p0.busy;
  p0Element("prepare").disabled = p0.busy || p0.uncertain || !p0.nonce;
  p0Element("generate").disabled = p0.busy || p0.uncertain || !p0.nonce || !p0.prepared || p0.liveBinding === "NONE" ||
    p0.prepared?.context?.institutional_resolution?.status === "CONTENT_GAP";
  p0Element("consent-send").disabled = p0.busy || p0.uncertain || !p0.nonce || !p0.consent ||
    !p0Element("consent-transfer").checked || !p0Element("consent-cost").checked ||
    !p0ConsentMatches(p0.consent, p0.prepared);
  for (const id of ["teacher", "revise", "validate", "save"])
    p0Element(id).disabled = p0.busy || p0.uncertain || !p0.view;
  for (const id of ["revise", "validate"]) p0Element(id).disabled ||= !p0.nonce;
  p0Element("teacher").disabled ||= !!p0.dirty;
  for (const id of ["save", "validate"]) p0Element(id).disabled ||= !!p0.dirty;
  p0Element("media-apply").disabled = p0.busy || p0.uncertain || !p0.nonce || !p0.view || !!p0.view.course_chapter || p0.mediaBinding !== "LOCAL_DIAGRAM_OR_NO_MEDIA";
  for (const id of ["open", "modify", "check", "correction", "marking", "export"])
    document.getElementById("card-" + id).disabled = p0.busy || p0.uncertain || !p0.view ||
      (id === "correction" && !p0.view.questions.length && !p0.view.course_chapter) ||
      (id === "marking" && p0.view.pedagogical_context.resource_type !== "ASSESSMENT") ||
      (["export", "check"].includes(id) && !!p0.dirty);
}
async function p0Fetch(path, body = null, contract = "R6-P0-HTTP-LOCAL-1.0") {
  const options = {method: body ? "POST" : "GET", credentials: "omit", cache: "no-store",
    redirect: "error", headers: {"X-Local-Intent": "conversation-v1"}};
  if (body) {
    await p0EnsureConnected();
    options.headers["Content-Type"] = "application/json; charset=utf-8";
    options.headers["X-R2-Nonce"] = p0.nonce;
    options.body = JSON.stringify(body);
  }
  return localBoundedRequest(path, options, async response => {
  const envelope = await response.json();
  if (!response.ok || envelope?.meta?.contract_id !== contract) {
    const error = new Error(envelope?.error?.code || "P0_REFUSED");
    error.confirmedRefusal = envelope?.meta?.contract_id === contract && response.status < 500 &&
      envelope?.error?.code !== "P0_OUTCOME_UNKNOWN";
    throw error;
  }
  return envelope.data;
  }, path === "/api/v2/p0/generate" || path === "/api/v2/p0/consent-generate" ? 150000 :
    path === "/api/v2/p0" || path === "/api/v2/p0/media" || /^\/api\/v2\/p0\/(versions\/|notion-evidence\?)/.test(path) ? 60000 : 10000);
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
    p0Element("status").textContent = error.localPrecondition ?
      "Connexion locale indisponible. Aucun envoi de commande ; reconnectez-vous explicitement avant de reprendre." :
      error.localTimedOut && !mutation ? "La consultation locale a dépassé son délai. Aucun envoi de commande ; reprenez la consultation explicitement." :
      "Action non confirmée : " + error.message +
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
  } else if (context.level.startsWith("BTS_")) {
    const frame = p0InstitutionalFrame();
    const activity = frame?.elements.find(e => e.id === p0Element("program-question").value);
    let process = activity;
    for (let i = 0; process && process.element_type !== "PROCESS" && i < frame.elements.length; i++)
      process = frame.elements.find(e => e.id === process.parent_ref);
    if (!activity || !process || process.element_type !== "PROCESS" || !p0Element("depth").value)
      throw Object.assign(new Error("P0_INSTITUTIONAL_CONTEXT_REQUIRED"), {confirmedRefusal: true});
    context.contract_id = "P0-CONTEXT-2.0";
    context.discipline = "Comptabilité et gestion";
    context.institutional = {contract_id: "BTS-INSTITUTIONAL-CONTEXT-1.0",
      program_ref: frame.program_ref, program_version: frame.program_version, process_ref: process.id,
      activity_ref: activity.id, competency_refs: [...p0Element("capacities").selectedOptions].map(o => o.value),
      notion_refs: [...p0Element("program-notions").selectedOptions].map(o => o.value),
      depth: p0Element("depth").value, local_year: context.level};
    context.institutional_resolution = null;
    context.local_progression = {chapter: p0Element("local-chapter").value.trim() || null,
      sequence: p0Element("local-sequence").value.trim() || null, week: p0Element("local-week").value.trim() || null};
  }
  return context;
}
function p0InstitutionalFrame() {
  if (p0Element("level").value.startsWith("BTS_"))
    return (p0.institutionalCatalog?.bts_frameworks || []).find(f => f.program_version === p0Element("frame").value);
  return (p0.institutionalCatalog?.frames || []).find(f => f.program_version === p0Element("frame").value && f.level === p0Element("level").value);
}
function p0InstitutionalOptions() {
  const stmg = p0Element("level").value.endsWith("STMG");
  const bts = p0Element("level").value.startsWith("BTS_");
  p0Element("institutional").hidden = !(stmg || bts);
  p0Element("discipline").readOnly = stmg || bts;
  for (const id of ["frame", "program-question", "program-notions", "depth"]) p0Element(id).required = stmg || bts;
  p0Element("element-label").textContent = bts ? "Processus et activité du référentiel" : "Question du programme";
  p0Element("capacities-label").textContent = bts ? "Compétences de cette activité" : "Capacités rattachées à cette question";
  const select = p0Element("frame"); select.replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Choisir l’enseignement exact"; select.append(empty);
  for (const frame of p0.institutionalCatalog?.frames || []) {
    if (frame.level !== p0Element("level").value) continue;
    const option = document.createElement("option"); option.value = frame.program_version;
    option.textContent = frame.label + " · " + frame.version_label; select.append(option);
  }
  if (bts) for (const frame of p0.institutionalCatalog?.bts_frameworks || []) {
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
  const bts = p0Element("level").value.startsWith("BTS_");
  if (bts) p0Element("discipline").value = "Comptabilité et gestion";
  const select = p0Element("program-question"); select.replaceChildren();
  const empty = document.createElement("option"); empty.value = ""; empty.textContent = bts ? "Choisir l’activité" : "Choisir la question"; select.append(empty);
  for (const question of frame?.questions || []) {
    const option = document.createElement("option"); option.value = question.question_ref;
    option.textContent = question.label + (question.theme_ref ? "" : " · thème à renseigner"); select.append(option);
  }
  if (bts) for (const activity of frame?.elements || []) {
    if (!["ACTIVITY", "SUB_ACTIVITY"].includes(activity.element_type)) continue;
    const option = document.createElement("option"); option.value = activity.id;
    option.textContent = activity.official_code + " · " + activity.official_label; select.append(option);
  }
  p0InstitutionalCapacityOptions();
}
function p0InstitutionalCapacityOptions() {
  const frame = p0InstitutionalFrame();
  const question = frame?.questions?.find(q => q.question_ref === p0Element("program-question").value);
  const select = p0Element("capacities"); select.replaceChildren();
  for (const capacity of frame?.capacities || []) {
    if (![p0Element("program-question").value, question?.theme_ref].includes(capacity.question_ref)) continue;
    const option = document.createElement("option"); option.value = capacity.capacity_ref; option.textContent = capacity.label; select.append(option);
  }
  if (p0Element("level").value.startsWith("BTS_")) {
    const scope = new Set([p0Element("program-question").value]);
    for (let i = 0; i < (frame?.elements.length || 0); i++) {
      let changed = false;
      for (const e of frame.elements) if (scope.has(e.parent_ref) && !scope.has(e.id)) {scope.add(e.id); changed = true;}
      if (!changed) break;
    }
    for (const competency of frame?.elements || []) if (scope.has(competency.id) && competency.element_type === "COMPETENCY") {
      const option = document.createElement("option"); option.value = competency.id; option.textContent = competency.official_label; select.append(option);
    }
  }
  p0Element("program-status").textContent = (frame?.authority === "UNATTESTED" ?
    "Snapshot local : provenance officielle à compléter. Aucune génération tant que les rattachements ne sont pas admis." :
    "Les capacités et rattachements seront contrôlés dans ce programme exact.") +
    (question && !question.theme_ref ? " Thème non renseigné dans la source : la question est sélectionnable, mais la génération reste bloquée." : "");
  if (p0Element("level").value.startsWith("BTS_")) p0Element("program-status").textContent =
    "Le processus, l’activité et les compétences seront vérifiés dans le référentiel exact. L’année BTS est une progression locale ; elle n’est pas prescrite par ce référentiel.";
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
  p0.contextRevision += 1;
  p0.prepared = null; p0ClearConsent(); p0Controls();
}
p0Element("form").addEventListener("input", p0Invalidate);
p0Element("form").addEventListener("change", p0Invalidate);
function p0SourceNotionOptions() {
  const selected = [...p0Element("program-notions").selectedOptions];
  p0Element("source-notion").replaceChildren(); p0Element("source-choices").replaceChildren();
  const empty = document.createElement("option"); empty.value="";empty.textContent="Choisir une notion du contexte";
  p0Element("source-notion").append(empty);
  for (const notion of selected) {const option=document.createElement("option");option.value=notion.value;
    option.textContent=notion.textContent;p0Element("source-notion").append(option);}
  if (selected.length===1) p0Element("source-notion").value=selected[0].value;
}
p0Element("program-notions").addEventListener("change",p0SourceNotionOptions);
// UI eligibility is a projection; Application independently reauthenticates admission.
function p0CanonicalJSON(value, depth = 0) {
  if (depth > 8) throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
  if (value === null || typeof value === "boolean") return JSON.stringify(value);
  if (typeof value === "string" && value.length <= 4096) return JSON.stringify(value);
  if (typeof value === "number" && Number.isFinite(value)) return JSON.stringify(value);
  if (Array.isArray(value) && value.length <= 256)
    return "[" + value.map(item => p0CanonicalJSON(item, depth + 1)).join(",") + "]";
  if (value && Object.prototype.toString.call(value) === "[object Object]") {
    const keys = Object.keys(value).sort();
    if (keys.length <= 64 && keys.every(key => /^[A-Za-z0-9_]+$/.test(key) && key !== "__proto__"))
      return "{" + keys.map(key => JSON.stringify(key) + ":" + p0CanonicalJSON(value[key], depth + 1)).join(",") + "}";
  }
  throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
}
function p0ClosedFields(value, fields) {
  return value && !Array.isArray(value) && Object.prototype.toString.call(value) === "[object Object]" &&
    Object.keys(value).sort().join("|") === [...fields].sort().join("|");
}
function p0LocalContextRows(value = []) {
  const fields = ["schema", "selection", "selection_sha256", "notion_id", "object_ref", "object_kind",
    "passage_ref", "version_or_checksum", "excerpt_sha256", "provenance", "source_status", "available_authority",
    "authority_basis", "canonical_notion_reference", "source_entry_scope_sha256", "canonical_notion_entry_scope_sha256",
    "canonical_institutional_resolution_sha256", "context_enrichment", "admission_basis", "manifest_sha256"];
  const anchorFields = ["notion_id", "object_ref", "object_kind", "passage_ref", "version_or_checksum", "excerpt_sha256",
    "provenance", "source_status", "available_authority", "authority_basis"];
  const hash = value => typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
  const text = value => typeof value === "string" && value.length > 0 && value.length <= 512;
  const selections = {
    "STMG-INSTITUTIONAL-CONTEXT-1.0": ["contract_id", "frame", "education_level", "series", "teaching_subject",
      "program_ref", "program_version", "program_component", "specific_track", "theme_ref", "question_ref",
      "capacity_refs", "notion_refs", "depth"],
    "BTS-INSTITUTIONAL-CONTEXT-1.0": ["contract_id", "program_ref", "program_version", "process_ref",
      "activity_ref", "competency_refs", "notion_refs", "depth", "local_year"]};
  const seen = new Set();
  if (!Array.isArray(value) || value.length > 20000) throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
  for (const row of value) {
    const anchor = row?.canonical_notion_reference;
    if (!p0ClosedFields(row, fields) || row.schema !== "P0-LOCAL-REFERENCE-CONTEXT-ROW-1.0" ||
        !p0ClosedFields(anchor, anchorFields) || row.context_enrichment !== false ||
        row.admission_basis !== "OWNER_ADMITTED_EXACT_LOCAL_CONTEXT" ||
        !["PEDAGOGICAL_CONTENT", "METHOD"].includes(row.object_kind) ||
        row.available_authority !== "UNKNOWN" || anchor.available_authority !== "UNKNOWN" ||
        row.authority_basis !== "NOT_ATTESTED_BY_APPLICATION" || anchor.authority_basis !== "NOT_ATTESTED_BY_APPLICATION" ||
        anchor.object_kind !== "NOTION" || anchor.notion_id !== row.notion_id || anchor.object_ref !== row.notion_id ||
        ![row.notion_id, row.object_ref, row.passage_ref, row.version_or_checksum, row.authority_basis,
          anchor.passage_ref, anchor.version_or_checksum, anchor.authority_basis].every(text) ||
        ![row.selection_sha256, row.excerpt_sha256, row.source_entry_scope_sha256,
          row.canonical_notion_entry_scope_sha256, row.canonical_institutional_resolution_sha256,
          row.manifest_sha256, anchor.excerpt_sha256].every(hash) ||
        !row.selection || !p0ClosedFields(row.selection, selections[row.selection.contract_id] || []) ||
        !selections[row.selection.contract_id] ||
        !Array.isArray(row.selection.notion_refs) || row.selection.notion_refs.length !== 1 ||
        row.selection.notion_refs[0] !== row.notion_id ||
        ![row.provenance, row.source_status, anchor.provenance, anchor.source_status].every(v =>
          v && !Array.isArray(v) && Object.prototype.toString.call(v) === "[object Object]"))
      throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
    p0CanonicalJSON(row);
    const key = p0CanonicalJSON([row.selection, row.notion_id, row.object_ref, row.object_kind, row.passage_ref, row.version_or_checksum]);
    if (seen.has(key)) throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
    seen.add(key);
  }
  return value;
}
async function p0TextSHA256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
}
async function p0LocalReferenceEligible(item, data, selection) {
  if (p0.localReferenceContextBinding !== "EXPLICIT_OWNER_LOCAL_CONTEXT" || !selection) return false;
  const identity = (row, passage) => passage && passage.excerpt_truncated === false &&
    row.notion_id === data.notion_id && passage.selection?.notion_id === row.notion_id &&
    ["object_ref", "object_kind", "passage_ref", "version_or_checksum", "excerpt_sha256"].every(key => row[key] === passage[key]) &&
    passage.selection.passage_ref === row.passage_ref && row.available_authority === data.available_authority &&
    row.available_authority === passage.available_authority && row.authority_basis === passage.authority_basis &&
    p0CanonicalJSON(row.provenance) === p0CanonicalJSON(passage.provenance) &&
    p0CanonicalJSON(row.source_status) === p0CanonicalJSON(passage.source_status);
  const selectedJSON = p0CanonicalJSON(selection);
  const rows = (p0.localReferenceContexts || []).filter(row =>
    p0CanonicalJSON(row.selection) === selectedJSON && identity(row, item));
  if (rows.length !== 1 || data.items.filter(passage => identity(rows[0], passage)).length !== 1) return false;
  const row = rows[0], anchors = data.items.filter(passage => identity(row.canonical_notion_reference, passage));
  if (anchors.length !== 1) return false;
  return row.selection_sha256 === await p0TextSHA256(selectedJSON) &&
    row.excerpt_sha256 === await p0TextSHA256(item.excerpt) &&
    row.canonical_notion_reference.excerpt_sha256 === await p0TextSHA256(anchors[0].excerpt);
}
p0Element("source-load").addEventListener("click",()=>p0Run(async()=>{
  const notion = p0Element("source-notion").value;
  const revision = p0.contextRevision;
  if (!notion || ![...p0Element("program-notions").selectedOptions].some(option=>option.value===notion))
    throw Object.assign(new Error("Choisissez une notion de votre contexte pour consulter ses sources"),{confirmedRefusal:true});
  const data = await p0Fetch("/api/v2/p0/notion-evidence?notion_id="+encodeURIComponent(notion),null,"P0-NOTION-EVIDENCE-HTTP-1.0");
  if (revision !== p0.contextRevision || notion !== p0Element("source-notion").value || data.notion_id!==notion || !Array.isArray(data.items) ||
      data.items.length>256 || data.available_authority!=="UNKNOWN")
    throw new Error("P0_NOTION_SOURCE_RESPONSE_BINDING");
  if (data.items.some(item => item.selection?.notion_id!==notion || item.selection.passage_ref!==item.passage_ref ||
      typeof item.excerpt!=="string" || !item.excerpt || item.excerpt_truncated!==false ||
      !["NOTION", "PEDAGOGICAL_CONTENT", "METHOD"].includes(item.object_kind)))
    throw new Error("P0_NOTION_SOURCE_RESPONSE_BINDING");
  let selection = null;
  if (p0.localReferenceContextBinding === "EXPLICIT_OWNER_LOCAL_CONTEXT") {
    try { selection = p0Context().institutional; } catch { /* Consultation remains available without a complete context. */ }
  }
  const eligibility = await Promise.all(data.items.map(item => p0LocalReferenceEligible(item, data, selection)));
  if (revision !== p0.contextRevision || notion !== p0Element("source-notion").value)
    throw new Error("P0_NOTION_SOURCE_RESPONSE_BINDING");
  const region=p0Element("source-choices");region.replaceChildren();
  appendSearchText(region,"p","Passages disponibles. Leur identité et leur présence ne valent pas admission comme source officielle.");
  for (const [index, item] of data.items.entries()) {
    const article=document.createElement("article");
    appendSearchText(article,"h4",item.object_kind==="NOTION" ? "Notion — "+p0Element("source-notion").selectedOptions[0].textContent :
      item.object_kind==="METHOD" ? "Méthode" : "Contenu pédagogique");
    appendSearchText(article,"p",item.excerpt);
    const details=document.createElement("details");appendSearchText(details,"summary","Provenance, version et statut");
    appendSearchText(details,"pre",JSON.stringify({object_ref:item.object_ref,passage_ref:item.passage_ref,
      version:item.version_or_checksum,excerpt_sha256:item.excerpt_sha256,provenance:item.provenance,
      source_status:item.source_status,authority:data.available_authority},null,2));article.append(details);
    const button=document.createElement("button");button.type="button";button.textContent="Sélectionner ce passage exact";
    const bts = p0Element("level").value.startsWith("BTS_");
    const canonical = item.object_kind==="NOTION" && item.object_ref===notion;
    const localContextMode = p0.localReferenceContextBinding === "EXPLICIT_OWNER_LOCAL_CONTEXT";
    const selectable = localContextMode ? eligibility[index] : canonical || !bts;
    button.disabled = !selectable;
    if (!selectable) appendSearchText(article,"p","Passage consultable ; son utilisation comme source de préparation n’est pas admise dans ce contexte exact.");
    if (eligibility[index]) appendSearchText(article,"p","Utilisation locale admise pour ce contexte exact. L’autorité du contenu reste non attestée ; ce passage n’est pas une source officielle.");
    button.addEventListener("click",()=>{
      if (!selectable || p0.busy || p0.uncertain || p0.contextRevision!==revision || p0Element("source-notion").value!==notion) return;
      p0Element("search-query").value="";p0Element("notion-id").value=item.selection.notion_id;
      p0Element("search-passage").value=item.selection.passage_ref;p0Element("reference").value="";
      p0.prepared=null;p0ClearConsent();p0Controls();
      p0Element("status").textContent="Source exacte sélectionnée. Confirmez votre contexte pour préparer la ressource.";
      uxMessage("assistant",p0Element("status").textContent);
    });article.append(button);region.append(article);
  }
  if (!data.items.length) appendSearchText(region,"p","Aucun passage complet utilisable pour cette notion.");
  if (data.exclusions?.length) appendSearchText(region,"p",data.exclusions.length+
    " passage(s) exclus : consultez leur disposition dans Sources & contexte.");
  document.getElementById("drawer-identities").textContent=JSON.stringify(data,null,2);
  p0Element("status").textContent="Sources de la notion affichées. Sélectionnez le passage adapté à votre travail.";
}));
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
    const revision = p0.contextRevision;
    const prepared = await p0Fetch("/api/v2/p0/prepare", {command_id: p0Command(), context: p0Context(), reference});
    if (revision !== p0.contextRevision) {
      p0Element("status").textContent = "Le contexte a changé pendant la préparation. Confirmez la demande actuelle avant de continuer.";
      return;
    }
    p0.prepared = prepared;
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
  p0.editInputs.push(input);
  parent.append(text, input); return input;
}
function p0CourseFields(region, chapter, teacher = false) {
  if (teacher) {
    (chapter.teacher_answers || []).forEach((answer, i) => {
      for (const [key, label] of [["expected_answer", "Réponse"], ["rationale", "Explication"],
        ["vigilance", "Vigilance"], ["remediation", "Remédiation"]])
        p0Field(region, "p0-course-teacher-" + key + "-" + i, label + " " + answer.id, answer[key]);
    });
    return;
  }
  p0Field(region, "p0-course-context-title", "Titre du contexte", chapter.context.title, false);
  p0Field(region, "p0-course-context-text", "Situation d’apprentissage", chapter.context.text);
  for (const [field, keys] of [["documents", [["title", "Titre du document"], ["text", "Texte du document"]]],
    ["questions", [["prompt", "Consigne"]]],
    ["concepts", [["definition", "Définition"], ["explanation", "Explication"], ["example", "Exemple"]]],
    ["parts", [["title", "Titre de partie"]]]])
    chapter[field].forEach((row, i) => keys.forEach(([key, label]) =>
      p0Field(region, "p0-course-" + field + "-" + key + "-" + i, label + " " + row.id, row[key])));
  p0Field(region, "p0-course-synthesis", "Synthèse du cours", chapter.synthesis);
  appendSearchText(region, "p", "Les sources et les liens du cours sont conservés. Une modification affectant un visuel existant nécessite sa révision explicite.");
}
function p0CourseEdits(chapter, teacher = null) {
  const changed = (before, after) => before !== after;
  const patch = {};
  const story = {};
  for (const key of ["title", "text"]) {
    const value = document.getElementById("p0-course-context-" + key).value;
    if (changed(chapter.context[key], value)) story[key] = value;
  }
  if (Object.keys(story).length) patch.context = story;
  const fields = [["documents", ["title", "text"]], ["questions", ["prompt"]],
    ["concepts", ["definition", "explanation", "example"]], ["parts", ["title"]]];
  for (const [field, keys] of fields) {
    const rows = chapter[field].map((row, i) => {
      const edited = {id: row.id};
      keys.forEach(key => { const value = document.getElementById("p0-course-" + field + "-" + key + "-" + i).value;
        if (changed(row[key], value)) edited[key] = value; });
      return edited;
    }).filter(row => Object.keys(row).length > 1);
    if (rows.length) patch[field] = rows;
  }
  const synthesis = document.getElementById("p0-course-synthesis").value;
  if (changed(chapter.synthesis, synthesis)) patch.synthesis = synthesis;
  if (teacher) {
    const answers = teacher.teacher_answers.map((row, i) => {
      const edited = {id: row.id};
      for (const key of ["expected_answer", "rationale", "vigilance", "remediation"]) {
        const value = document.getElementById("p0-course-teacher-" + key + "-" + i).value;
        if (changed(row[key], value)) edited[key] = value;
      }
      return edited;
    }).filter(row => Object.keys(row).length > 1);
    if (answers.length) patch.teacher_answers = answers;
  }
  return {title: document.getElementById("p0-edit-title").value, course_edits: patch};
}
function p0MediaOptions(view) {
  const selected = view.pedagogical_context.institutional || {};
  const capacities = view.pedagogical_context.institutional_resolution?.capacities || [];
  for (const [id, options] of [["media-anchor", view.sections.map(s => [s.section_id, s.heading])],
    ["media-capacity", (selected.capacity_refs || selected.competency_refs || []).map(ref => [ref,
      capacities.find(row => (row.capacity_ref || row.competency_ref) === ref)?.label || ref])],
    ["media-objective", view.pedagogical_context.objectives.map(text => [text, text])]]) {
    const select = p0Element(id); select.replaceChildren();
    options.forEach(([value, label]) => { const option = document.createElement("option");
      option.value = value; option.textContent = label; select.append(option); });
  }
  for (const id of ["media-reason", "media-nodes", "media-caption"]) p0Element(id).value = "";
  p0Element("media-mode").value = "NO_MEDIA"; p0Element("diagram-fields").hidden = true;
  p0Element("media-required").checked = false;
  p0Element("media-note").textContent = view.course_chapter ?
    "Ce cours structuré conserve son dossier de visuels existant. Les changements de contenu qui affectent un visuel sont refusés ; sa révision reste distincte." :
    "Le schéma local utilise les étapes que vous fournissez. Relisez sa pertinence ; aucune image fournisseur n’est générée.";
}
function p0MediaSelection(view) {
  const reason = p0Element("media-reason").value.trim();
  if (!reason) throw new Error("P0_MEDIA_JUSTIFICATION_REQUIRED");
  if (p0Element("media-mode").value === "NO_MEDIA") return {mode: "NO_MEDIA", reason};
  if (p0Element("media-mode").value !== "LOCAL_DIAGRAM") throw new Error("P0_MEDIA_MODE_REJECTED");
  const selected = view.pedagogical_context.institutional;
  const capacity = p0Element("media-capacity").value;
  const objective = p0Element("media-objective").value;
  const anchor = p0Element("media-anchor").value;
  if (view.pedagogical_context.institutional_resolution?.status !== "RESOLVED_ADMITTED" || !selected ||
      !(selected.capacity_refs || selected.competency_refs || []).includes(capacity) ||
      !view.pedagogical_context.objectives.includes(objective) ||
      !view.sections.some(section => section.section_id === anchor)) throw new Error("P0_MEDIA_CONTEXT_REQUIRED");
  const labels = p0Element("media-nodes").value.split("\n").map(text => text.trim());
  const caption = p0Element("media-caption").value.trim();
  if (labels.length !== 4 || labels.some(text => !text || text.length > 70) || new Set(labels).size !== 4 || !caption)
    throw new Error("P0_MEDIA_FOUR_DISTINCT_STEPS_REQUIRED");
  const brief = {contract_id: "VISUAL-BRIEF-1.0", visual_id: "VISUAL_" + p0Command().slice(0, 8).toUpperCase(),
    production_ref: view.production_ref, section_ref: anchor, learning_objective: objective,
    institutional_capability_ref: capacity, notion_refs: selected.notion_refs,
    visual_type: "FLOWCHART", pedagogical_function: reason, content_description: reason,
    must_show: labels, must_not_show: [], caption, alt_text: caption,
    student_visibility: true, teacher_visibility: true, preferred_position: "AFTER_DOCUMENT",
    source_policy: "LOCAL_DETERMINISTIC", style_policy: "COURSE_LOCAL_DIAGRAM_V1",
    diagram: {layout: "FLOW", nodes: labels.map((label, i) => ({id: "N" + i, label, detail: "", icon: "NONE"})),
      edges: labels.slice(1).map((_, i) => ({source: "N" + i, target: "N" + (i + 1), label: ""})), note: caption}};
  // Each detail is explicit visible content, required by the existing visual contract.
  brief.diagram.nodes.forEach(node => { node.detail = node.label; });
  return {mode: "LOCAL_DIAGRAM", entries: [{brief, required: p0Element("media-required").checked,
    dependency_refs: ["section:" + anchor]}]};
}
p0Element("media-mode").addEventListener("change", () => {
  p0Element("diagram-fields").hidden = p0Element("media-mode").value !== "LOCAL_DIAGRAM";
});
p0Element("media-form").addEventListener("submit", event => {
  event.preventDefault();
  p0Run(async () => {
    if (p0.dirty) throw new Error("P0_MEDIA_SAVE_LOCAL_EDITS_FIRST");
    const parent = p0Identity(); const selection = p0MediaSelection(p0.view);
    const result = await p0Fetch("/api/v2/p0/media", {command_id: p0Command(), ...parent, selection}, "P0-LOCAL-MEDIA-HTTP-1.0");
    if (!p0DisplayedVersion(parent) || result.view?.production_ref !== parent.production_ref ||
        result.view?.lineage?.parent_version_ref !== parent.version_ref || result.provider_attempts !== 0)
      throw new Error("P0_MEDIA_VERSION_CHANGED");
    p0Render(result.view, result.quality);
    p0Element("status").textContent = "Choix du visuel conservé dans une nouvelle version. Relisez puis sauvegardez cette version ; le parent est inchangé.";
  }, true);
});
function p0Render(view, quality = null) {
  p0.view = view; p0.teacher = null;
  p0.editInputs = [];
  p0.dirty = false;
  uxQuality(quality, view);
  const region = p0Element("review"); region.replaceChildren();
  p0Element("teacher-content").replaceChildren();
  appendSearchText(region, "p", "Préparation à relire avant usage pédagogique.");
  uxProductionCard(view);
  p0MediaOptions(view);
  p0Field(region, "p0-edit-title", "Titre", view.title, false);
  if (view.course_chapter) { p0CourseFields(region, view.course_chapter); return; }
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
function p0DisplayedVersion(target) {
  const region = document.getElementById("drawer-quality");
  return p0.view?.production_ref === target.production_ref && p0.view?.version_ref === target.version_ref &&
    p0.view?.bundle_sha256 === target.bundle_sha256 && region.dataset.productionRef === target.production_ref &&
    region.dataset.versionRef === target.version_ref && region.dataset.bundleSha256 === target.bundle_sha256;
}
function p0ClearConsent() {
  p0.consent = null; p0Element("consent").hidden = true;
  p0Element("consent-transfer").checked = p0Element("consent-cost").checked = false;
  for (const id of ["consent-summary", "consent-body", "consent-identities"]) p0Element(id).replaceChildren();
}
function p0ConsentMatches(result, prepared, now = Date.now()) {
  const preview = result?.preview;
  if (!prepared || result.state !== "LOCAL_OPERATOR_CONSENT_REQUIRED" ||
      result.provider_attempts !== 0 || result.review_state !== "NOT_RUN" ||
      result.source_status !== "RESERVE" || result.consent_actor !== "LOCAL_OPERATOR_DELEGATED" ||
      !/^[0-9a-f]{64}$/.test(result.preview_sha256 || "") ||
      preview?.schema !== "P0-PRODUCT-CONSENT-PREVIEW-1.0" ||
      preview.preparation_ref !== prepared.preparation_ref || preview.preparation_sha256 !== prepared.preparation_sha256 ||
      typeof preview.request_body_utf8 !== "string" || preview.request_body_utf8.length > 512 * 1024 ||
      !/^[0-9a-f]{64}$/.test(preview.request_sha256 || "") ||
      !Array.isArray(preview.source_receipts) || !preview.source_receipts.length ||
      !/^0\.\d{1,6}$/.test(preview.cost_bound_usd || "") || Number(preview.cost_bound_usd) > 0.14 ||
      !Number.isFinite(Date.parse(preview.expires_at_utc)) || now >= Date.parse(preview.expires_at_utc))
    return false;
  return true;
}
function p0ConsentPreview(result, prepared) {
  if (!p0ConsentMatches(result, prepared)) throw new Error("P0_CONSENT_PREVIEW_BINDING");
  const preview = result.preview, body = JSON.parse(preview.request_body_utf8);
  if (body.model !== "gpt-5.6-terra" || body.max_output_tokens !== 4096 ||
      body.store !== false || body.stream !== false || body.background !== false)
    throw new Error("P0_CONSENT_PROVIDER_PROFILE");
  p0ClearConsent(); p0.consent = result; p0Element("consent").hidden = false;
  const summary = p0Element("consent-summary");
  appendSearchText(summary, "p", "OpenAI · gpt-5.6-terra · https://api.openai.com/v1/responses");
  appendSearchText(summary, "p", "Coût maximal de cette création : " + preview.cost_bound_usd +
    " USD. Budget disponible : " + result.remaining_budget_usd + " USD · " + result.remaining_calls + " création(s) restante(s).");
  appendSearchText(summary, "p", "Contenu transmis : " + preview.request_bytes + " octets. Accord valable jusqu’au " +
    new Date(preview.expires_at_utc).toLocaleString("fr-FR") + ".");
  appendSearchText(summary, "p", "Sources sélectionnées pour cette demande :");
  for (const receipt of preview.source_receipts)
    appendSearchText(summary, "p", JSON.stringify(receipt));
  appendSearchText(summary, "p", "Une seule tentative, aucun renvoi automatique. Revue indépendante non exécutée ; relecture enseignante nécessaire.");
  p0Element("consent-body").textContent = preview.request_body_utf8;
  p0Element("consent-identities").textContent = JSON.stringify({...preview, request_body_utf8:undefined}, null, 2);
}
function p0GeneratedResult(result) {
  if (result.state !== "CANDIDATE") throw Object.assign(new Error("P0_GENERATION_NOT_CONFIRMED"), {confirmedRefusal:true});
  p0Render(result.view, result.agentic?.quality); p0.prepared = null; p0ClearConsent();
  p0Element("status").textContent = result.publication?.state === "APPLICATION_SAVED" ?
    "Ressource reçue et conservée dans votre bibliothèque. Relisez ses contrôles et ses réserves avant usage." :
    "Candidate reçue. Relisez et sauvegardez la version exacte ; aucune promotion effectuée.";
}
p0Element("generate").addEventListener("click", () => p0Run(async () => {
  if (p0.normalConsentBinding === "EXPLICIT_PRODUCT_PERMISSION") {
    const prepared = p0.prepared;
    const result = await p0Fetch("/api/v2/p0/consent-preview", {command_id:p0Command(),
      preparation_ref:prepared.preparation_ref, preparation_sha256:prepared.preparation_sha256});
    if (p0.prepared !== prepared) throw new Error("P0_CONSENT_PREPARATION_CHANGED");
    p0ConsentPreview(result, prepared);
    p0Element("status").textContent = "Vérifiez le contenu et le coût maximal, puis confirmez cet envoi dans l’application.";
    return;
  }
  const result = await p0Fetch("/api/v2/p0/generate", {command_id: p0Command(),
    preparation_ref: p0.prepared.preparation_ref, preparation_sha256: p0.prepared.preparation_sha256});
  if (result.state === "CANDIDATE") {
    p0GeneratedResult(result);
  } else { p0Element("status").dataset.state = "unavailable";
    p0Element("status").textContent = "Génération indisponible : autorisation requise. Aucun transport fournisseur n’est lié à cette composition hors ligne."; }
}, p0.normalConsentBinding !== "EXPLICIT_PRODUCT_PERMISSION", "generating"));
for (const id of ["consent-transfer", "consent-cost"]) p0Element(id).addEventListener("change", p0Controls);
p0Element("consent-cancel").addEventListener("click", () => {p0ClearConsent(); p0Controls();});
p0Element("consent-send").addEventListener("click", () => p0Run(async () => {
  const consent = p0.consent, prepared = p0.prepared;
  if (!p0ConsentMatches(consent, prepared) || !p0Element("consent-transfer").checked || !p0Element("consent-cost").checked)
    throw Object.assign(new Error("P0_CONSENT_REQUIRED"), {confirmedRefusal:true});
  p0ClearConsent();
  const result = await p0Fetch("/api/v2/p0/consent-generate", {command_id:p0Command(),
    preparation_ref:prepared.preparation_ref, preparation_sha256:prepared.preparation_sha256,
    preview_sha256:consent.preview_sha256, transfer_accepted:true, cost_bound_accepted:true});
  p0GeneratedResult(result);
}, true, "generating"));
p0Element("teacher").addEventListener("click", () => p0Run(async () => {
  if (p0.dirty) throw Object.assign(new Error("Conservez votre modification avant de recharger les réponses professeur"), {confirmedRefusal:true});
  const target = p0Identity();
  const teacher = await p0Fetch("/api/v2/p0/versions/" + target.production_ref + "/" + target.version_ref + "/teacher");
  if (p0.dirty) throw Object.assign(new Error("Une modification est en cours. Les réponses consultées ne remplacent pas votre travail"), {confirmedRefusal:true});
  if (!p0DisplayedVersion(target) || teacher.production_ref !== target.production_ref ||
      teacher.version_ref !== target.version_ref || teacher.bundle_sha256 !== target.bundle_sha256)
    throw new Error("P0_TEACHER_VERSION_CHANGED");
  p0.teacher = teacher;
  const region = p0Element("teacher-content"); region.replaceChildren();
  appendSearchText(region, "h3", "Compagnons professeur — consultation séparée");
  if (teacher.course_chapter) { p0CourseFields(region, teacher.course_chapter, true); return; }
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
  const edits = p0.view.course_chapter ? p0CourseEdits(p0.view.course_chapter, p0.teacher?.course_chapter) : {title: document.getElementById("p0-edit-title").value,
    sections: p0.view.sections.map((s, i) => ({...s, heading: document.getElementById("p0-edit-heading-" + i).value,
      text: document.getElementById("p0-edit-section-" + i).value})),
    questions: p0.view.questions.map((q, i) => ({...q, prompt: document.getElementById("p0-edit-question-" + i).value,
      options: q.options.length ? document.getElementById("p0-edit-options-" + i).value.split("\n") : []}))};
  if (p0.teacher && !p0.view.course_chapter) {
    edits.corrections = p0.teacher.corrections.map((c, i) => ({...c,
      expected_answer: document.getElementById("p0-edit-answer-" + i).value,
      rationale: document.getElementById("p0-edit-rationale-" + i).value}));
    edits.marking = p0.teacher.marking.map((m, i) => ({...m, points: document.getElementById("p0-edit-points-" + i).value,
      criteria: document.getElementById("p0-edit-criteria-" + i).value.split("\n")}));
  }
  const parent = p0Identity();
  const result = await p0Fetch("/api/v2/p0/revise", {command_id: p0Command(), ...parent, edits});
  if (!p0DisplayedVersion(parent)) { p0Element("status").textContent = "Révision reçue pour une autre version consultée. Rouvrez sa version exacte."; return; }
  p0Render(result.view, result.quality); p0Element("status").textContent = "Nouvelle version conservée ; la version parente est inchangée.";
}, true));
p0Element("validate").addEventListener("click", () => p0Run(async () => {
  const target = p0Identity();
  const report = await p0Fetch("/api/v2/p0/validate", {command_id: p0Command(), ...target});
  if (!p0DisplayedVersion(target)) { p0Element("status").textContent = "Vérification conservée pour sa version exacte ; la version consultée a changé."; return; }
  uxQuality(report.quality, target);
  p0Element("status").textContent = "Vérification structurelle : " + report.status + ". Aucune validation pédagogique ni promotion.";
}, true, "validating"));
async function p0SaveVersion() {
  if (p0.dirty) throw Object.assign(new Error("Conservez d’abord vos modifications dans une nouvelle version"), {confirmedRefusal:true});
  const refs = {production_ref: p0.view.production_ref, version_ref: p0.view.version_ref};
  await r4Fetch("/api/v2/conversation/saved", refs);
  await r4Refresh(); r4Versions.value = refs.production_ref + "/" + refs.version_ref;
  await r4Open(); p0Element("status").textContent = "Version sauvegardée et rouverte. Exports disponibles dans l’espace de conservation.";
}
p0Element("save").addEventListener("click", () => p0Run(p0SaveVersion, true, "saving"));
function p0ConnectionReady() {
  return p0.connected === true && typeof p0.nonce === "string" && /^[A-Za-z0-9_-]{43}$/.test(p0.nonce);
}
async function p0EnsureConnected() {
  if (p0ConnectionReady()) return;
  try {
    await p0Connect();
    if (!p0ConnectionReady()) throw new Error("P0_LOCAL_CONNECTION_REQUIRED");
  } catch (error) {
    throw Object.assign(new Error("P0_LOCAL_CONNECTION_UNAVAILABLE"), {
      confirmedRefusal: true, localPrecondition: true, localTimedOut: !!error.localTimedOut
    });
  }
}
async function p0Connect() {
  if (p0ConnectionPromise) return p0ConnectionPromise;
  p0.connected = false; p0.nonce = null;
  p0.liveBinding = "NONE"; p0.normalConsentBinding = "NONE"; p0.mediaBinding = "NONE";
  p0.localReferenceContextBinding = "NONE"; p0.localReferenceContexts = [];
  p0Element("generate").textContent = "Génération indisponible : connexion locale à établir";
  p0ConnectionPromise = (async () => {
    const metadata = await p0Fetch("/api/v2/p0");
    if (metadata?.state !== "READY" || metadata.authority !== "NONE" ||
        typeof metadata.transport_nonce !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(metadata.transport_nonce) ||
        !Array.isArray(metadata.references) || !metadata.references.every(ref => ref && typeof ref.title === "string") ||
        !["NONE", "EXPLICIT_PORT"].includes(metadata.live_binding) ||
        !["NONE", "EXPLICIT_PRODUCT_PERMISSION"].includes(metadata.normal_consent_binding || "NONE") ||
        !["NONE", "LOCAL_DIAGRAM_OR_NO_MEDIA"].includes(metadata.media_binding) ||
        !["NONE", "EXPLICIT_OWNER_LOCAL_CONTEXT"].includes(metadata.local_reference_context_binding || "NONE"))
      throw new Error("P0_LOCAL_METADATA_REJECTED");
    const localContexts = p0LocalContextRows(metadata.local_reference_contexts);
    const localBinding = metadata.local_reference_context_binding || "NONE";
    if ((localBinding === "NONE" && localContexts.length) ||
        (localBinding === "EXPLICIT_OWNER_LOCAL_CONTEXT" && metadata.normal_consent_binding !== "EXPLICIT_PRODUCT_PERMISSION"))
      throw new Error("P0_LOCAL_REFERENCE_METADATA_REJECTED");
    p0.references = metadata.references; p0.institutionalCatalog = metadata.institutional_catalog;
    p0InstitutionalOptions();
    p0.liveBinding = metadata.live_binding;
    p0.normalConsentBinding = metadata.normal_consent_binding || "NONE";
    p0.mediaBinding = metadata.media_binding;
    p0.localReferenceContextBinding = localBinding; p0.localReferenceContexts = localContexts;
    p0Element("generate").textContent = metadata.live_binding === "NONE" ? "Génération indisponible dans cette composition" :
      p0.normalConsentBinding === "EXPLICIT_PRODUCT_PERMISSION" ? "Examiner l’envoi et son coût" : "Demander la génération autorisée";
    p0Element("reference").replaceChildren();
    const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Choisir une référence";
    p0Element("reference").append(empty);
    p0.references.forEach((ref, i) => {
      const option = document.createElement("option"); option.value = String(i);
      option.textContent = ref.title; p0Element("reference").append(option);
    });
    p0.nonce = metadata.transport_nonce; p0.connected = true;
    p0Element("status").textContent = "Contexte prêt à renseigner. Aucune génération autorisée.";
  })();
  try { return await p0ConnectionPromise; }
  finally { p0ConnectionPromise = null; }
}
p0Element("connect").addEventListener("click", () => p0Run(p0Connect));
let p0InitialConnectionPending = true;
const p0InitialConnection = p0Run(p0Connect).finally(() => { p0InitialConnectionPending = false; });

// Conversational shell: proposals are deterministic and explicitly confirmed.
// Business versions are saved through Application, never in browser storage.
const uxRequests = [];
const uxNames = {COURSE: "Cours", EXERCISE: "Exercice", OPEN_QUESTIONS: "Questions ouvertes", QCM: "QCM", QUIZ: "Quiz", ASSESSMENT: "Évaluation",
  FIRST_STMG: "Première STMG", FINAL_STMG: "Terminale STMG", BTS_CG_YEAR_1: "BTS CG première année", BTS_CG_YEAR_2: "BTS CG deuxième année"};
function uxShow(name) {
  if (typeof uxDraftConfirm === "function" && !uxDraftConfirm()) return false;
  document.querySelectorAll("[data-panel]").forEach(panel => { panel.hidden = panel.dataset.panel !== name; });
  document.querySelectorAll("[data-view]").forEach(button => { button.setAttribute("aria-current", button.dataset.view === name ? "page" : "false"); });
  document.getElementById("workspace-title").textContent = {home: "Accueil", prepare: "Atelier de création", conversations: "Conversations", productions: "Productions", library: "Bibliothèque", settings: "Réglages"}[name];
  document.getElementById("main-content").focus({preventScroll:true});
  return true;
}
function uxMessage(role, text) {
  const messages = document.getElementById("preparation-messages");
  if (messages.lastElementChild?.textContent === text) return;
  appendSearchText(messages, "li", text, "message-" + role);
  while (messages.children.length > 64) messages.firstElementChild.remove();
}
async function proposePreparation(text) {
  const command = p0Command();
  const result = await p0Fetch("/api/v2/p0/intention", {command_id:command, intention:text});
  if (result.contract_id !== "P0-INTENTION-PROPOSAL-1.0" || result.command_id !== command ||
      result.confirmation_required !== true || result.provider_attempts !== 0 ||
      result.implementation !== "DETERMINISTIC_APPLICATION_PROPOSAL" || result.authority !== "NONE")
    throw new Error("P0_INTENTION_RESPONSE_REJECTED");
  return result;
}
function uxContext(context) {
  const region = document.getElementById("drawer-context"); region.replaceChildren();
  appendSearchText(region, "p", (uxNames[context.question_mode || context.resource_type] || "Type à préciser") + " · " + (uxNames[context.level] || "Niveau à préciser"));
  appendSearchText(region, "p", context.discipline || "Discipline à préciser");
  if (context.institutional) {
    const selected = context.institutional, resolved = context.institutional_resolution;
    const bts = selected.contract_id === "BTS-INSTITUTIONAL-CONTEXT-1.0";
    const level = bts ? (selected.local_year === "BTS_CG_YEAR_1" ? "BTS CG première année (progression locale)" : "BTS CG deuxième année (progression locale)") : selected.education_level === "PREMIERE" ? "Première STMG" : "Terminale STMG";
    appendSearchText(region, "p", "Niveau : " + level);
    appendSearchText(region, "p", "Enseignement : " + context.discipline.split(" — ")[0]);
    if (selected.program_component === "COMMON") appendSearchText(region, "p", "Partie : Enseignement commun");
    if (selected.program_component === "SPECIFIC") appendSearchText(region, "p", "Enseignement spécifique : " + context.discipline.split(" — ").slice(1).join(" — "));
    appendSearchText(region, "p", (bts ? "Référentiel : " : "Programme : ") + context.discipline + " — " + level + " · " + (resolved?.version_label || "version sélectionnée à vérifier"));
    appendSearchText(region, "h4", "Cadre institutionnel");
    if (bts) {
      appendSearchText(region, "p", (resolved?.process?.official_label || "Processus à vérifier") + " · " + (resolved?.activity?.official_label || "Activité à vérifier"));
      appendSearchText(region, "p", "Compétences : " + ((resolved?.competencies || []).map(c => c.official_label).join(" · ") || "rattachements à compléter"));
      appendSearchText(region, "p", "Répartition annuelle locale, sans prescription officielle de BTS CG1 ou CG2.");
    } else {
      appendSearchText(region, "p", (resolved?.theme?.official_label || (/^theme:\d+$/.test(selected.theme_ref || "") ? "Thème " + selected.theme_ref.replace("theme:", "") : "Thème non renseigné")) + " · " + (resolved?.question?.official_label || "question sélectionnée à vérifier"));
      appendSearchText(region, "p", "Capacités : " + ((resolved?.capacities || []).map(c => c.label).join(" · ") || "rattachements à compléter"));
    }
    appendSearchText(region, "p", "Notions : " + ((resolved?.notions || []).map(n => n.label).join(" · ") || "sélection à vérifier") + " · " +
      ({DISCOVERY:"Découverte", APPLICATION:"Application", ANALYSIS:"Analyse"}[selected.depth] || "profondeur à préciser"));
    if (resolved?.gaps?.length) appendSearchText(region, "p", "Lacunes institutionnelles : provenance, capacités ou liens encore non admis. Génération bloquée.");
    appendSearchText(region, "p", "Profondeur proposée pour l’activité, distincte d’une exigence officielle.");
    appendSearchText(region, "h4", "Construction pédagogique");
    if (context.local_progression) {
      appendSearchText(region, "p", "Progression locale : " + Object.values(context.local_progression).filter(Boolean).join(" · "));
    }
  }
  appendSearchText(region, "p", (context.topics || []).join(" · "));
  if (context.duration_minutes) appendSearchText(region, "p", context.duration_minutes + " minutes · /" + context.total_points);
}
function uxQuality(quality, view = p0.view) {
  const labels = {SOURCES_OK: "Identité des sources contrôlée", SOURCES_INSUFFICISANTES: "Sources insuffisantes", CALCULS_VERIFIES: "Calculs vérifiés", ECHEC: "Preuve indépendante des calculs manquante", NON_APPLICABLE: "Aucun calcul requis par le travail qualitatif explicite", A_DETERMINER: "Applicabilité des calculs à déterminer", CONSIGNE_COUVERTE: "Couverture examinée", PARTIELLE: "Couverture à examiner", REVUE_OK: "Revue technique sans réserve", RESERVE: "Revue pédagogique en attente ou avec réserves", HUMAN_REVIEW_REQUIRED: "Relecture enseignante nécessaire"};
  const region = document.getElementById("drawer-quality"); region.replaceChildren();
  region.dataset.productionRef = view?.production_ref || "";
  region.dataset.versionRef = view?.version_ref || "";
  region.dataset.bundleSha256 = view?.bundle_sha256 || "";
  if (!quality) { appendSearchText(region, "p", "Non vérifié pour cette version. Les rapports conservés couvrent uniquement leur version exacte. Relecture enseignante nécessaire."); return; }
  for (const key of ["sources", "calculations", "instruction", "review", "human_review"]) appendSearchText(region, "p", labels[quality[key]] || "Non vérifié");
}
function uxPreparation(prepared) {
  uxContext(prepared.context); uxQuality(prepared.agentic?.quality, null);
  const region = document.getElementById("drawer-sources"); region.replaceChildren();
  const passages = prepared.agentic?.evidence_pack?.passages || [];
  appendSearchText(region, "h4", "Sources de contenu");
  const pack = prepared.agentic?.evidence_pack;
  if (pack?.content_authority_status) appendSearchText(region, "p", "Passages sélectionnés : leur catégorie d’autorité disciplinaire ou pédagogique reste à vérifier.");
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
  const blocks = view.course_chapter ? uxCourseBlocks(view.course_chapter) :
    [...view.sections.flatMap(section => [{style: "Heading1", text: section.heading, anchor_ref: section.section_id}, {style: "Normal", text: section.text}]),
      ...view.questions.flatMap((question, i) => [{style: "Heading2", text: "Question " + (i + 1), anchor_ref: question.question_id}, {style: "Normal", text: question.prompt},
        ...question.options.map(option => ({style: "Normal", text: option}))])];
  classroomPreview(preview, blocks, view.media_assets || view.course_chapter?.media_assets || []);
  uxContext(context);
  document.getElementById("drawer-identities").textContent = JSON.stringify({production_ref: view.production_ref, version_ref: view.version_ref, bundle_sha256: view.bundle_sha256, references: view.references}, null, 2);
  document.getElementById("production-edit-panel").open = false;
}
function uxCourseBlocks(chapter) {
  const blocks = [{style:"Heading1",text:chapter.context.title,anchor_ref:"CONTEXT"},
    {style:"Normal",text:chapter.context.text}];
  const documents = new Map(chapter.documents.map(item=>[item.id,item]));
  const questions = new Map(chapter.questions.map(item=>[item.id,item]));
  const concepts = new Map(chapter.concepts.map(item=>[item.id,item]));
  const question = ref => {const item=questions.get(ref);if (!item) throw new Error("P0_COURSE_VIEW_BINDING");
    blocks.push({style:"Heading2",text:"Question "+item.number,anchor_ref:ref},{style:"Normal",text:item.prompt});
    if (item.response.table) blocks.push({style:"Normal",text:"",table:item.response.table});
    else blocks.push({style:"Normal",text:Array(item.response.lines).fill("………………………………………………………………").join("\n")});
  };
  const document = ref => {const item=documents.get(ref);if (!item) throw new Error("P0_COURSE_VIEW_BINDING");
    blocks.push({style:"Heading2",text:item.title,anchor_ref:ref},{style:"Normal",text:item.text});
    if (item.table) blocks.push({style:"Normal",text:"",table:item.table});
  };
  chapter.parts.forEach(part=>{
    blocks.push({style:"Heading1",text:part.title});
    part.document_ids.forEach(document);
    for (const role of ["observation", "analysis"]) {
      blocks.push({style:"Heading2",text:role === "observation" ? "Observer" : "Analyser"});
      part[role].forEach(question);
    }
    part.concept_ids.forEach(ref=>{const item=concepts.get(ref);if (!item) throw new Error("P0_COURSE_VIEW_BINDING");
      blocks.push({style:"Heading2",text:item.notion,anchor_ref:ref},{style:"Normal",text:item.definition},
        {style:"Normal",text:item.explanation},{style:"Normal",text:item.example});});
    blocks.push({style:"Heading2",text:"Réinvestir"});part.reinvestment.forEach(question);
  });
  blocks.push({style:"Heading1",text:"Tester ses connaissances"});chapter.knowledge_check.forEach(question);
  blocks.push({style:"Heading1",text:"À retenir"},{style:"Normal",text:chapter.synthesis},
    {style:"Heading1",text:chapter.transfer.title});
  chapter.transfer.document_ids.forEach(document);chapter.transfer.question_ids.forEach(question);
  return blocks;
}
function uxMediaAssets(region, assets) {
  assets.forEach(asset => {
    if (asset.mime_type !== "image/png" || !/^iVBORw0KGgo/.test(asset.bytes_base64) ||
        asset.bytes_base64.length > 1500000 || !/^[0-9a-f]{64}$/.test(asset.png_sha256))
      throw new Error("P0_MEDIA_VIEW_REJECTED");
    const figure = document.createElement("figure"); const image = document.createElement("img");
    image.src = "data:image/png;base64," + asset.bytes_base64; image.alt = asset.alt_text;
    image.width = asset.width; image.height = asset.height;
    figure.append(image); appendSearchText(figure, "figcaption", asset.caption); region.append(figure);
  });
}
async function uxTeacherCard(kind) {
  await p0Run(async () => {
    const target = p0Identity();
    const teacher = await p0Fetch("/api/v2/p0/versions/" + target.production_ref + "/" + target.version_ref + "/teacher");
    if (!p0DisplayedVersion(target) || teacher.production_ref !== target.production_ref ||
        teacher.version_ref !== target.version_ref || teacher.bundle_sha256 !== target.bundle_sha256)
      throw new Error("P0_TEACHER_VERSION_CHANGED");
    const region = document.getElementById("production-card-teacher-preview");
    region.replaceChildren(); region.hidden = false;
    appendSearchText(region, "h3", kind === "correction" ? "Correction — document professeur séparé" : "Barème — document professeur séparé");
    const blocks = uxTeacherBlocks(p0.view, teacher, kind);
    classroomPreview(region,blocks,teacher.media_assets || teacher.course_chapter?.media_assets || []);
    p0Element("status").textContent = "Document professeur consulté séparément. Le sujet élève est inchangé.";
  });
}
function uxTeacherBlocks(view, teacher, kind) {
  const chapter=teacher.course_chapter;
  if (chapter) {
    if (kind!=="correction") throw new Error("P0_COURSE_MARKING_NOT_AVAILABLE");
    const answers=new Map(chapter.teacher_answers.map(answer=>[answer.id,answer]));
    const blocks=uxCourseBlocks(chapter), result=[];
    for (const block of blocks) {
      result.push(block);
      if (answers.has(block.anchor_ref)) {
        const answer=answers.get(block.anchor_ref);
        result.push({style:"Normal",text:answer.expected_answer},{style:"Normal",text:answer.rationale},
          {style:"Normal",text:"Point de vigilance : "+answer.vigilance},{style:"Normal",text:"Remédiation : "+answer.remediation});
      }
    }
    return result;
  }
  const blocks=view.sections.flatMap(section=>[{style:"Heading1",text:section.heading,anchor_ref:section.section_id},
    {style:"Normal",text:section.text}]);
  const companions=new Map((kind==="correction" ? teacher.corrections : teacher.marking).map(item=>[item.question_id,item]));
  for (const [index,question] of view.questions.entries()) {
    const companion=companions.get(question.question_id);
    if (!companion) throw new Error("P0_TEACHER_VIEW_BINDING");
    blocks.push({style:"Heading2",text:"Question "+(index+1),anchor_ref:question.question_id},
      {style:"Normal",text:question.prompt});
    if (kind==="correction") blocks.push({style:"Normal",text:companion.expected_answer},{style:"Normal",text:companion.rationale});
    else blocks.push({style:"Normal",text:companion.points+" points"},
      ...companion.criteria.map(text=>({style:"Normal",text})));
  }
  return blocks;
}
function uxSavedCard(saved) {
  const view = saved.record.view;
  uxContext(view.context || view.pedagogical_context || {});
  document.getElementById("drawer-identities").textContent = JSON.stringify({production_ref: view.production_ref, version_ref: view.version_ref,
    record_sha256: saved.record_sha256, provenance: saved.record.provenance, reviews: saved.record.reviews, validations: saved.record.validations}, null, 2);
  const region = document.getElementById("drawer-sources"); region.replaceChildren();
  appendSearchText(region, "h4", "Sources de contenu");
  appendSearchText(region, "p", (view.references || []).length + " référence(s) conservée(s). Leur identité ne vaut pas admission disciplinaire ou pédagogique.");
  const context = view.context || view.pedagogical_context || {};
  const resolved = context.institutional_resolution;
  if (resolved?.document_provenance) {
    appendSearchText(region, "p", "Source institutionnelle distincte : " + resolved.document_provenance.title);
    appendSearchText(region, "p", "Admission du propriétaire sur la version exacte conservée ; la recette enseignante reste à réaliser.");
  } else appendSearchText(region, "p", "Aucune autorité institutionnelle attestée dans cette version historique.");
  uxQuality(null, view);
}
document.querySelectorAll("[data-view]").forEach(button => button.addEventListener("click", () => uxShow(button.dataset.view)));
document.getElementById("new-preparation").addEventListener("click", () => {
  if (!uxShow("prepare")) return;
  document.getElementById("preparation-prompt").value = ""; document.getElementById("preparation-prompt").focus();
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
  const text = document.getElementById("preparation-prompt").value.trim(); if (!text || !uxDraftConfirm()) return;
  p0Run(async () => {
    const response = await proposePreparation(text);
    uxMessage("user", text);
    if (response.state === "OUT_OF_SCOPE") {
      const actions = {MODIFY:"Modifier", REVIEW:"Vérifier", EXPORT:"Exporter"};
      uxMessage("assistant", "Cette demande concerne une version active : ouvrez votre production puis utilisez « " +
        (actions[response.unsupported_operation] || "Ouvrir") + " ». La préparation actuelle est conservée.");
      return;
    }
    const proposed = response.proposal;
    p0.view = null; p0.teacher = null;
    for (const id of ["drawer-context", "drawer-sources", "drawer-identities"]) document.getElementById(id).replaceChildren();
    appendSearchText(document.getElementById("drawer-context"), "p", "Nouvelle demande proposée, contexte à confirmer.");
    appendSearchText(document.getElementById("drawer-sources"), "p", "Aucune source confirmée pour cette demande.");
    uxQuality(null, null);
    document.getElementById("production-card").hidden = true;
    uxRequests.push(text); if (uxRequests.length > 32) uxRequests.shift();
    for (const id of ["recent-preparations", "session-conversations"]) {
      const region = document.getElementById(id); region.replaceChildren();
      [...uxRequests].reverse().forEach(request => { const item = document.createElement("li"), button = document.createElement("button");
        button.type = "button"; button.textContent = request; button.addEventListener("click", () => {
          if (uxShow("prepare")) document.getElementById("preparation-prompt").value = request;
        }); item.append(button); region.append(item); });
    }
    p0Element("family").value = proposed.family || ""; p0Element("level").value = proposed.level || "";
    p0Element("difficulty").value = proposed.difficulty || ""; p0Element("topics").value = proposed.topics.join("\n");
    p0Element("objectives").value = proposed.objectives.join("\n");
    p0Element("discipline").value = proposed.level?.startsWith("BTS_") ? "Comptabilité et gestion" : "";
    p0InstitutionalOptions();
    p0Element("duration").value = proposed.duration_minutes ?? ""; p0Element("points").value = proposed.total_points ?? "";
    p0Element("family").dispatchEvent(new Event("change")); p0Invalidate();
    document.getElementById("preparation-parameters").open = true;
    uxMessage("assistant", "Proposition déterministe Application, à confirmer. Choisissez l’enseignement, les capacités et les notions exactes dans le catalogue, puis les références utiles.");
    if (proposed.level?.startsWith("BTS_")) uxMessage("assistant", "Choisissez le référentiel exact, son processus et son activité, puis les compétences et notions avant de confirmer le contexte. L’année BTS relève de la progression locale.");
    const names = {family:"type de ressource", level:"niveau exact", topics:"sujet", objectives:"objectifs", difficulty:"difficulté",
      duration_minutes:"durée", total_points:"barème", duration_constraint_application:"application de la durée hors évaluation",
      points_constraint_application:"application du barème hors évaluation"};
    if (response.missing_fields.length) uxMessage("assistant", "À préciser : " + response.missing_fields.map(field => names[field] || field).join(", ") + ".");
    for (const ambiguity of response.ambiguities) uxMessage("assistant", "Choix à confirmer pour " +
      (names[ambiguity.field] || ambiguity.field) + " : " + ambiguity.candidates.map(value => uxNames[value] || value).join(" ou ") + ".");
    if (proposed.family !== "ASSESSMENT" && (proposed.duration_minutes || proposed.total_points))
      uxMessage("assistant", "La durée et le barème demandés restent visibles ici. Leur application hors évaluation n’est pas prise en charge par le contrat actuel ; aucune valeur n’est effacée silencieusement.");
    p0Element("status").textContent = response.state === "CONTEXT_PROPOSED" ?
      "Proposition reçue. Confirmez le contexte et sélectionnez les références." : "Proposition reçue avec des précisions nécessaires.";
    document.getElementById("preparation-prompt").value = "";
  });
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

// Persistent content is always read via Application. These are presentation pointers only.
function uxDraftConfirm() {
  if (!p0.dirty) return true;
  if (!window.confirm("Des modifications ne sont pas encore conservées. Les abandonner pour changer de vue ou de document ?")) return false;
  p0.dirty = false;
  if (p0.view) p0Render(p0.view);
  return true;
}
function p0Edited() {
  p0.dirty = true; p0Controls();
  p0Element("status").textContent = "Modification en cours. Conservez-la dans une nouvelle version avant de vérifier, sauvegarder ou exporter.";
}
document.getElementById("production-edit-panel").addEventListener("input", p0Edited);
p0Element("teacher-content").addEventListener("input", p0Edited);
window.addEventListener("beforeunload", event => {
  if (!p0.dirty && !document.getElementById("home-prompt").value.trim() &&
      !document.getElementById("preparation-prompt").value.trim()) return;
  event.preventDefault(); event.returnValue = "";
});
function uxHomeVersions(versions) {
  const region = document.getElementById("home-productions"); region.replaceChildren();
  if (!versions.length) appendSearchText(region, "p", "Aucune production sauvegardée dans cette bibliothèque.");
  for (const version of versions.slice(-6).reverse()) {
    const card = document.createElement("article"); card.className = "resource-card";
    appendSearchText(card, "span", version.origin === "LOCAL_APPLICATION" ? "Candidate à relire" : "Document conservé · lecture seule", "badge");
    appendSearchText(card, "h3", version.title || "Production conservée");
    appendSearchText(card, "p", (uxNames[version.context?.level] || "Contexte conservé") + " · Version " + version.version_ref.slice(-8));
    const open = document.createElement("button"); open.type = "button"; open.className = "btn small"; open.textContent = "Ouvrir";
    open.addEventListener("click", () => { if (!uxShow("productions")) return;
      r4Versions.value = version.production_ref + "/" + version.version_ref; r4Run(r4Open); });
    card.append(open); region.append(card);
  }
  const exact = r4Record && versions.find(v => v.production_ref === r4Record.record.view.production_ref && v.version_ref === r4Record.record.view.version_ref);
  document.getElementById("home-resume").hidden = !exact;
  if (exact) {
    document.getElementById("home-resume-title").textContent = exact.title || "Dernière version consultée";
    document.getElementById("home-resume-context").textContent = "Dernière version consultée · " + exact.version_ref.slice(-8);
  }
}
document.getElementById("home-resume-open").addEventListener("click", () => {
  if (r4Record && uxShow("productions")) {
    r4Versions.value = r4Record.record.view.production_ref + "/" + r4Record.record.view.version_ref; r4Run(r4Open);
  }
});
document.getElementById("home-composer").addEventListener("submit", event => {
  event.preventDefault(); if (!uxShow("prepare")) return;
  document.getElementById("preparation-prompt").value = document.getElementById("home-prompt").value;
  document.getElementById("home-prompt").value = "";
  document.getElementById("preparation-composer").requestSubmit();
});
document.querySelectorAll("[data-start-family]").forEach(button => button.addEventListener("click", () => {
  if (!uxShow("prepare")) return;
  document.getElementById("preparation-prompt").value = "Prépare " + uxNames[button.dataset.startFamily].toLocaleLowerCase("fr") + " ";
  document.getElementById("preparation-prompt").focus();
}));
async function p0ResumeSaved() {
  if (r4ResumePending) return;
  const saved = r4Record;
  if (p0.busy && !p0InitialConnectionPending) {
    r4Status.textContent = "Une action est déjà en cours dans l’atelier. Reprenez explicitement après sa fin.";
    return;
  }
  r4ResumePending = true; r4Controls();
  try {
    if (p0InitialConnectionPending) {
      r4Status.textContent = "Reprise demandée : attente de la connexion locale de l’atelier…";
      await p0InitialConnection;
    }
    if (p0.busy) {
      r4Status.textContent = "Une action est déjà en cours dans l’atelier. Reprenez explicitement après sa fin.";
      return;
    }
    if (r4Record !== saved) {
      r4Status.textContent = "La sélection sauvegardée a changé. Reprenez explicitement la version souhaitée.";
      return;
    }
    await p0Run(async () => {
      if (!uxDraftConfirm()) {
        p0Element("status").textContent = "Reprise annulée. Les modifications de l’atelier sont conservées.";
        return;
      }
      if (!saved || saved.record.origin !== "LOCAL_APPLICATION") throw new Error("P0_SAVED_SOURCE_REJECTED");
      const selected = saved.record.view;
      await p0EnsureConnected();
      if (r4Record !== saved) throw new Error("P0_SAVED_VERSION_CHANGED");
      uxShow("prepare");
      p0Element("status").textContent = "Lecture de la version et vérification de sa chaîne de parents…";
      const view = await p0Fetch("/api/v2/p0/versions/" + selected.production_ref + "/" + selected.version_ref);
      if (r4Record !== saved || view.production_ref !== selected.production_ref || view.version_ref !== selected.version_ref ||
          view.bundle_sha256 !== selected.bundle_sha256) throw new Error("P0_SAVED_VERSION_CHANGED");
      p0Render(view, {sources:"RESERVE", human_review:"HUMAN_REVIEW_REQUIRED"});
      uxShow("prepare"); document.getElementById("production-edit-panel").open = false;
      p0Element("status").textContent = "Version exacte reprise pour édition locale. Références historiques non revalidées ; aucun droit fournisseur restauré.";
    });
    r4Status.textContent = p0Element("status").textContent;
  } finally { r4ResumePending = false; r4Controls(); }
}
document.getElementById("r4-resume").addEventListener("click", p0ResumeSaved);
