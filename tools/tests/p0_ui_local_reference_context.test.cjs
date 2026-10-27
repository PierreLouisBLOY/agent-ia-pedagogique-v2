"use strict";
// Execute shipped UI handlers with synthetic DOM/Application projections only.
// These fixtures confer no source admission, live permission or provider authority.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm"), crypto = require("node:crypto");
const assert = require("node:assert/strict"), {test} = require("node:test");
const fixture = fs.readFileSync(path.join(__dirname, "pr4_lifecycle_regressions.test.cjs"), "utf8");
const base = {require, __dirname, console, AbortController};
vm.createContext(base); vm.runInContext(fixture.slice(0, fixture.indexOf("for(const year")), base);
const asyncFixture = fs.readFileSync(path.join(__dirname, "p0_ui_async_binding.test.cjs"), "utf8");
vm.runInContext("const ctx = {harness:harness};\n" + asyncFixture.slice(asyncFixture.indexOf("const proposedSource="),
  asyncFixture.indexOf('test("metadata deadline')), base);
const canonical = value => Array.isArray(value) ? "[" + value.map(canonical).join(",") + "]" :
  value && typeof value === "object" ? "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}" : JSON.stringify(value);
const sha = value => crypto.createHash("sha256").update(value, "utf8").digest("hex");
function setup(level = "BTS_CG_YEAR_2", kind = "METHOD", family = "COURSE") {
  const h = base.harness(); h.ctx.crypto = {subtle:crypto.webcrypto.subtle}; h.ctx.TextEncoder = TextEncoder;
  h.ctx.p0.contextRevision = 0; h.pe("family").value = family; h.pe("level").value = level;
  h.pe("course-format").value = "EXPLAINED";
  if (level.endsWith("STMG")) {
    h.ctx.p0.institutionalCatalog.frames = [{level, frame:"SYNTHETIC_FRAME", education_level:level === "FIRST_STMG" ? "PREMIERE":"TERMINALE",
      teaching_subject:"SYNTHETIC_SUBJECT", program_ref:"program:synthetic", program_version:"version:synthetic",
      program_component:"SPECIALITE", specific_track:null, label:"SYNTHETIC", version_label:"TEST",
      questions:[{question_ref:"question:synthetic", theme_ref:"theme:synthetic", label:"SYNTHETIC"}],
      capacities:[{capacity_ref:"capacity:synthetic", question_ref:"question:synthetic", label:"SYNTHETIC"}]}];
    h.ctx.p0InstitutionalOptions(); h.pe("frame").value = "version:synthetic"; h.ctx.p0InstitutionalQuestionOptions();
    h.pe("program-question").value = "question:synthetic"; h.ctx.p0InstitutionalCapacityOptions();
    h.pe("capacities").selectedOptions = [{value:"capacity:synthetic"}];
    h.pe("program-notions").selectedOptions = [{value:"notion:test", textContent:"SYNTHETIC"}]; h.pe("depth").value = "APPLICATION";
  } else { h.ctx.p0InstitutionalOptions(); base.select(h); }
  h.pe("source-notion").value = "notion:test"; h.pe("source-notion").selectedOptions = [{value:"notion:test", textContent:"SYNTHETIC"}];
  const provenance = {authority_absolute:false, content_trust:"UNTRUSTED_CONTENT", source_kind:"SYNTHETIC"};
  const passage = (object_ref, object_kind, passage_ref, text, digit) => ({object_ref, object_kind, passage_ref,
    version_or_checksum:digit.repeat(64), excerpt:text, excerpt_sha256:sha(text), excerpt_truncated:false,
    provenance:{...provenance}, source_status:{validation_status:"UNKNOWN"}, available_authority:"UNKNOWN",
    authority_basis:"NOT_ATTESTED_BY_APPLICATION", selection:{notion_id:"notion:test", passage_ref}});
  const anchor = passage("notion:test", "NOTION", "synthetic:canonical", "SYNTHETIC CANONICAL NOTION", "a");
  const source = passage("source:synthetic", kind, "synthetic:content", "SYNTHETIC FULL CONTENT", "b");
  const selection = JSON.parse(JSON.stringify(h.ctx.p0Context().institutional));
  const rowIdentity = item => ({notion_id:"notion:test", ...Object.fromEntries(["object_ref", "object_kind", "passage_ref",
    "version_or_checksum", "excerpt_sha256", "provenance", "source_status", "available_authority", "authority_basis"].map(key => [key, item[key]]))});
  const row = structuredClone({schema:"P0-LOCAL-REFERENCE-CONTEXT-ROW-1.0", selection, selection_sha256:sha(canonical(selection)),
    ...rowIdentity(source), canonical_notion_reference:rowIdentity(anchor), source_entry_scope_sha256:"c".repeat(64),
    canonical_notion_entry_scope_sha256:"d".repeat(64), canonical_institutional_resolution_sha256:"e".repeat(64),
    manifest_sha256:"f".repeat(64), context_enrichment:false, admission_basis:"OWNER_ADMITTED_EXACT_LOCAL_CONTEXT"});
  const data = {notion_id:"notion:test", available_authority:"UNKNOWN", authority_basis:"NOT_ATTESTED_BY_APPLICATION", items:[anchor, source], exclusions:[]};
  h.ctx.p0.localReferenceContextBinding = "EXPLICIT_OWNER_LOCAL_CONTEXT";
  h.ctx.p0.localReferenceContexts = h.ctx.p0LocalContextRows([row]); h.ctx.nextResponse = data;
  return {h, row, data, anchor, source, selection};
}
const button = h => h.pe("source-choices").children.at(-1).children.findLast(child => child.listeners.click);
for (const level of ["FIRST_STMG", "FINAL_STMG", "BTS_CG_YEAR_1", "BTS_CG_YEAR_2"])
  for (const family of ["COURSE", "EXERCISE", "ASSESSMENT", "OPEN_QUESTIONS", "QCM", "QUIZ"])
    test("exact locally admitted full passage remains UNKNOWN: " + level + "/" + family, async () => {
      const {h} = setup(level, family === "COURSE" ? "PEDAGOGICAL_CONTENT":"METHOD", family);
      await h.pe("source-load").listeners.click[0](); const selected = button(h);
      assert.equal(selected.disabled, false); assert.match(h.pe("source-choices").textContent, /pas une source officielle/);
      selected.listeners.click[0](); assert.equal(h.pe("search-passage").value, "synthetic:content");
      assert.equal(h.calls.length, 1); assert.equal(h.ctx.p0.prepared, null);
      assert.match(h.pe("source-choices").textContent, /"authority": "UNKNOWN"/);
    });
const mutations = {
  wrong_program: ({row}) => {row.selection.program_version = "version:other"; row.selection_sha256 = sha(canonical(row.selection));},
  wrong_year: ({row}) => {row.selection.local_year = "BTS_CG_YEAR_1"; row.selection_sha256 = sha(canonical(row.selection));},
  wrong_depth: ({row}) => {row.selection.depth = "ANALYSIS"; row.selection_sha256 = sha(canonical(row.selection));},
  wrong_capacity: ({row}) => {row.selection.competency_refs = ["competency:other"]; row.selection_sha256 = sha(canonical(row.selection));},
  wrong_selection_hash: ({row}) => {row.selection_sha256 = "0".repeat(64);},
  replaced_source: ({source}) => {source.object_ref = "source:other";},
  changed_version: ({source}) => {source.version_or_checksum = "0".repeat(64);},
  changed_excerpt: ({source}) => {source.excerpt += " CHANGED";},
  changed_source_hash: ({source}) => {source.excerpt_sha256 = "0".repeat(64);},
  changed_status: ({source}) => {source.source_status.validation_status = "VALIDATED";},
  changed_provenance: ({source}) => {source.provenance.authority_absolute = true;},
  changed_authority_basis: ({source}) => {source.authority_basis = "OFFICIAL";},
  changed_available_authority: ({source}) => {source.available_authority = "OFFICIAL";},
  missing_anchor: ({data}) => {data.items.shift();},
  anchor_alias: ({anchor}) => {anchor.object_ref = "notion:alias";},
  changed_anchor_text: ({anchor}) => {anchor.excerpt += " CHANGED";},
  changed_anchor_version: ({anchor}) => {anchor.version_or_checksum = "0".repeat(64);},
  changed_anchor_status: ({anchor}) => {anchor.source_status.validation_status = "VALIDATED";},
  duplicate_anchor: ({data, anchor}) => {data.items.push({...anchor});},
  duplicate_source: ({data, source}) => {data.items.push({...source});},
  missing_binding: ({h}) => {h.ctx.p0.localReferenceContexts = [];},
  absent_profile: ({h}) => {h.ctx.p0.localReferenceContextBinding = "NONE";}
};
for (const [name, mutate] of Object.entries(mutations)) test("no local source selection after " + name, async () => {
  const state = setup(); mutate(state); await state.h.pe("source-load").listeners.click[0]();
  // A duplicate anchor appended after the source changes its displayed position, so inspect all source buttons.
  const articles = state.h.pe("source-choices").children.filter(child => child.children.some(node => node.listeners.click));
  const content = articles.find(article => article.textContent.includes("SYNTHETIC FULL CONTENT"));
  assert(content); const denied = content.children.findLast(child => child.listeners.click); assert.equal(denied.disabled, true);
  denied.listeners.click[0](); assert.equal(state.h.pe("search-passage").value, ""); assert.equal(state.h.calls.length, 1);
});
for (const name of ["extra_row_field", "extra_anchor_field", "extra_selection_field", "duplicate_row", "malformed_hash", "official_authority", "enrichment", "wrong_admission"])
  test("metadata rejects complete list before any partial eligibility: " + name, () => {
    const {h, row} = setup(), rows = [structuredClone(row)];
    if (name === "extra_row_field") rows.push({...structuredClone(row), hidden:true});
    if (name === "extra_anchor_field") rows[0].canonical_notion_reference.hidden = true;
    if (name === "extra_selection_field") rows[0].selection.hidden = true;
    if (name === "duplicate_row") rows.push(structuredClone(row));
    if (name === "malformed_hash") rows[0].manifest_sha256 = "wrong";
    if (name === "official_authority") rows[0].available_authority = "OFFICIAL";
    if (name === "enrichment") rows[0].context_enrichment = true;
    if (name === "wrong_admission") rows[0].admission_basis = "IMPLICIT";
    assert.throws(() => h.ctx.p0LocalContextRows(rows), /P0_LOCAL_REFERENCE_METADATA_REJECTED/);
  });
test("context change during asynchronous hash comparison cannot publish or select a stale passage", async () => {
  const {h} = setup(); let resolve;
  let first = true;
  h.ctx.crypto.subtle = {digest:(...args) => {
    if (!first) return crypto.webcrypto.subtle.digest(...args);
    first = false; return new Promise(done => {resolve = () => crypto.webcrypto.subtle.digest(...args).then(done);});
  }};
  const pending = h.pe("source-load").listeners.click[0](); await new Promise(done => setImmediate(done));
  h.ctx.p0Invalidate(); resolve(); await pending;
  assert.equal(h.pe("source-choices").children.length, 0); assert.equal(h.pe("search-passage").value, "");
});
test("profile2 without current bindings keeps every passage consultable without a legacy selection fallback", async () => {
  for (const level of ["FIRST_STMG", "BTS_CG_YEAR_2"]) {
    const {h} = setup(level); h.ctx.p0.localReferenceContexts = [];
    await h.pe("source-load").listeners.click[0]();
    const buttons = h.pe("source-choices").children.flatMap(article => article.children.filter(child => child.listeners.click));
    assert.equal(buttons.length, 2); assert(buttons.every(button => button.disabled));
    for (const button of buttons) button.listeners.click[0]();
    assert.equal(h.pe("search-passage").value, ""); assert.equal(h.calls.length, 1);
  }
});
function metadata(row, binding = "EXPLICIT_OWNER_LOCAL_CONTEXT") {
  return {state:"READY", authority:"NONE", transport_nonce:"N".repeat(43), references:[],
    live_binding:"EXPLICIT_PORT", normal_consent_binding:"EXPLICIT_PRODUCT_PERMISSION", media_binding:"NONE",
    institutional_catalog:{frames:[], bts_frameworks:[], notions:[]}, local_reference_context_binding:binding,
    local_reference_contexts:row ? [structuredClone(row)]:[]};
}
for (const populated of [false, true]) test("connection installs the explicit profile2 mode only after the entire metadata validates: " + populated, async () => {
  const row = setup().row, value = metadata(populated ? row:null);
  const h = base.connectionHarness(async () => ({ok:true, status:200,
    json:async () => ({meta:{contract_id:"R6-P0-HTTP-LOCAL-1.0"}, data:value})}));
  await h.initial(); assert.equal(h.ctx.p0.connected, true);
  assert.equal(h.ctx.p0.localReferenceContextBinding, "EXPLICIT_OWNER_LOCAL_CONTEXT");
  assert.equal(h.ctx.p0.localReferenceContexts.length, populated ? 1:0);
  assert.equal(h.network.length, 1); assert.equal(h.network[0].options.method, "GET");
});
for (const mutation of ["binding_none_with_rows", "missing_permission", "invalid_second_row", "unknown_binding"])
  test("invalid local context metadata never installs a partial mode or issues POST: " + mutation, async () => {
    const value = metadata(setup().row);
    if (mutation === "binding_none_with_rows") value.local_reference_context_binding = "NONE";
    if (mutation === "missing_permission") value.normal_consent_binding = "NONE";
    if (mutation === "invalid_second_row") value.local_reference_contexts.push({...structuredClone(value.local_reference_contexts[0]), hidden:true});
    if (mutation === "unknown_binding") value.local_reference_context_binding = "UNKNOWN";
    const h = base.connectionHarness(async () => ({ok:true, status:200,
      json:async () => ({meta:{contract_id:"R6-P0-HTTP-LOCAL-1.0"}, data:value})}));
    await h.initial(); assert.equal(h.ctx.p0.connected, false); assert.equal(h.ctx.p0.nonce, null);
    assert.equal(h.ctx.p0.localReferenceContextBinding, "NONE"); assert.equal(h.ctx.p0.localReferenceContexts.length, 0);
    assert.equal(h.ctx.p0.uncertain, false); assert.equal(h.network.length, 1); assert.equal(h.network[0].options.method, "GET");
  });
