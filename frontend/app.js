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
