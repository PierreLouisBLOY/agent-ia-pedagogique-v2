"use strict";
// Shipped helpers and preparation handlers, with synthetic DOM/HTTP and a deterministic clock.
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const assert = require("node:assert/strict"), {test} = require("node:test");
const source = fs.readFileSync(path.join(__dirname, "../../frontend/app.js"), "utf8");
const transportSource = source.slice(source.indexOf("async function localBoundedRequest("), source.indexOf("async function conversationFetch(")) +
  source.slice(source.indexOf("async function p0Fetch("), source.indexOf("async function p0Run("));
function transport(ctx = {}) {
  let time = 0, id = 0;
  const timers = new Map(), calls = [];
  const state = Object.assign(ctx, {AbortController, p0EnsureConnected: async () => {}});
  state.p0 ??= {nonce: "SYNTHETIC"};
  state.setTimeout = (callback, milliseconds) => {timers.set(++id, {callback, at: time + milliseconds}); return id;};
  state.clearTimeout = timer => timers.delete(timer);
  state.fetch = (route, options) => {calls.push({route, options}); return state.reply(route, options);};
  vm.createContext(state); vm.runInContext(transportSource, state);
  return {ctx: state, calls, advance(ms) {
    time += ms;
    for (const [timer, value] of [...timers]) if (value.at <= time) {timers.delete(timer); value.callback();}
  }, timers};
}
const command = {command_id: "a".repeat(32), context: {synthetic: true}, reference: {synthetic: true}};
const response = data => ({ok: true, status: 200, json: async () => ({
  data, meta: {contract_id: "R6-P0-HTTP-LOCAL-1.0"}})});
const flush = async () => {for (let i = 0; i < 15; i++) await Promise.resolve();};
for (const route of ["/api/v2/p0/prepare", "/api/v2/p0/consent-preview"]) {
  test(route + " accepts one measured-duration response beyond the old 10s", async () => {
    const h = transport(); let finish;
    h.ctx.reply = () => new Promise(resolve => {finish = () => resolve(response({state: "LOCAL_READY"}));});
    const result = h.ctx.p0Fetch(route, command); await flush();
    h.advance(route.endsWith("consent-preview") ? 56172 : 28531);
    assert.equal(h.calls[0].options.signal.aborted, false);
    finish(); assert.equal((await result).state, "LOCAL_READY");
    assert.equal(h.calls.length, 1); assert.equal(h.timers.size, 0);
    assert.equal(h.calls[0].options.body, JSON.stringify(command));
  });
}
for (const route of ["/api/v2/p0/generate", "/api/v2/p0/consent-generate"]) {
  test(route + " retains its existing 150s bound without fallback", async () => {
    const h = transport(); let finish;
    h.ctx.reply = () => new Promise(resolve => {finish = () => resolve(response({state: "CANDIDATE"}));});
    const result = h.ctx.p0Fetch(route, command); await flush(); h.advance(60000);
    assert.equal(h.calls[0].options.signal.aborted, false);
    finish(); await result; assert.equal(h.calls.length, 1);
  });
}
for (const route of ["/api/v2/p0/prepare", "/api/v2/p0/consent-preview"])
for (const mode of ["headers", "body", "late-headers", "late-body"]) {
  test(route + " expiry " + mode + " remains bounded and never retries", async () => {
    const h = transport(); let finish, consumed = 0;
    h.ctx.reply = (route, options) => {
      const pending = () => new Promise((resolve, reject) => {
        finish = () => resolve(mode.endsWith("headers") ? response({state: "READY"}) :
          {data: {state: "READY"}, meta: {contract_id: "R6-P0-HTTP-LOCAL-1.0"}});
        if (!mode.startsWith("late")) options.signal.addEventListener("abort", () => reject(new Error("ABORTED")));
      });
      if (mode.endsWith("headers")) return pending();
      return Promise.resolve({ok: true, status: 200, json: () => {consumed++; return pending();}});
    };
    const result = h.ctx.p0Fetch(route, command); await flush();
    h.advance((route.endsWith("consent-preview") ? 150000 : 60000) - 1);
    assert.equal(h.calls[0].options.signal.aborted, false);
    h.advance(1);
    if (mode.startsWith("late")) finish();
    await assert.rejects(result, error => error.localTimedOut === true &&
      (route.endsWith("prepare") ? error.localCommandId === command.command_id : error.localCommandId === undefined));
    assert.equal(h.calls.length, 1); assert.equal(h.timers.size, 0);
    assert.equal(consumed, mode.endsWith("headers") ? 0 : 1);
  });
}
test("consent preview tolerates local verification beyond 60s without an automatic retry", async () => {
  const h = transport(); let finish;
  h.ctx.reply = () => new Promise(resolve => {finish = () => resolve(response({state: "LOCAL_OPERATOR_CONSENT_REQUIRED"}));});
  const result = h.ctx.p0Fetch("/api/v2/p0/consent-preview", command); await flush();
  h.advance(61000); assert.equal(h.calls[0].options.signal.aborted, false);
  finish(); assert.equal((await result).state, "LOCAL_OPERATOR_CONSENT_REQUIRED");
  assert.equal(h.calls.length, 1); assert.equal(h.timers.size, 0);
});
test("unlisted operations retain the closed 10s policy", async () => {
  const h = transport();
  h.ctx.reply = (route, options) => new Promise((resolve, reject) =>
    options.signal.addEventListener("abort", () => reject(new Error("ABORTED"))));
  const result = h.ctx.p0Fetch("/api/v2/p0/revise", command); await flush(); h.advance(10000);
  await assert.rejects(result, error => error.localTimedOut === true);
  assert.equal(h.calls.length, 1);
});
test("a refusal completed after expiry cannot clear uncertainty", async () => {
  const h = transport(); let finish;
  h.ctx.reply = () => ({ok: false, status: 409, json: () => new Promise(resolve => {finish = () => resolve({
    error: {code: "P0_REFERENCE_NOT_FOUND"}, meta: {contract_id: "R6-P0-HTTP-LOCAL-1.0"}});})});
  const result = h.ctx.p0Fetch("/api/v2/p0/prepare", command); await flush();
  h.advance(60000); finish();
  await assert.rejects(result, error => error.localTimedOut === true && error.confirmedRefusal === false &&
    error.localCommandId === command.command_id);
  assert.equal(h.calls.length, 1);
});
test("a refusal received within the bound remains a confirmed refusal", async () => {
  const h = transport();
  h.ctx.reply = () => ({ok: false, status: 409, json: async () => ({error: {code: "P0_REFERENCE_NOT_FOUND"},
    meta: {contract_id: "R6-P0-HTTP-LOCAL-1.0"}})});
  await assert.rejects(h.ctx.p0Fetch("/api/v2/p0/prepare", command), error =>
    error.confirmedRefusal === true && error.localTimedOut !== true);
  assert.equal(h.calls.length, 1);
});
const fixture = fs.readFileSync(path.join(__dirname, "pr4_lifecycle_regressions.test.cjs"), "utf8");
const base = {require, __dirname, console}; vm.createContext(base);
vm.runInContext(fixture.slice(0, fixture.indexOf("for(const year")), base);
function preparation() {
  const h = base.harness(); h.ctx.p0.contextRevision = 0; h.ctx.p0.nonce = "SYNTHETIC";
  h.ctx.p0.prepared = null;
  h.pe("family").value = "EXERCISE"; h.pe("level").value = "BTS_CG_YEAR_2";
  h.ctx.p0InstitutionalOptions(); base.select(h);
  h.pe("notion-id").value = "notion:test"; h.pe("search-passage").value = "synthetic:canonical";
  return {h, wire: transport(h.ctx)};
}
test("nominal preparation publishes its unchanged context once", async () => {
  const {h, wire} = preparation();
  wire.ctx.reply = (route, options) => response({context: JSON.parse(options.body).context, references: [],
    preparation_ref: "prep:" + "b".repeat(32), preparation_sha256: "c".repeat(64)});
  h.pe("form").dispatchEvent(new h.ctx.Event("submit")); await flush();
  assert.equal(h.ctx.p0.prepared.context.level, "BTS_CG_YEAR_2");
  assert.equal(h.ctx.p0.uncertain, false); assert.equal(wire.calls.length, 1);
});
test("expired preparation retains form, stops duplicate submit and rejects its late response", async () => {
  const {h, wire} = preparation(); let finish;
  wire.ctx.reply = (route, options) => new Promise(resolve => {finish = () => resolve(response({
    context: JSON.parse(options.body).context, references: [], preparation_ref: "prep:" + "b".repeat(32),
    preparation_sha256: "c".repeat(64)}));});
  h.pe("form").dispatchEvent(new h.ctx.Event("submit")); await flush();
  h.pe("form").dispatchEvent(new h.ctx.Event("submit")); await flush();
  assert.equal(wire.calls.length, 1, "Busy state blocks a second command");
  wire.advance(60000); finish(); await flush();
  assert.equal(h.ctx.p0.uncertain, true); assert.equal(h.ctx.p0.prepared, null);
  assert.equal(h.pe("level").value, "BTS_CG_YEAR_2");
  assert.equal(h.pe("search-passage").value, "synthetic:canonical");
  assert.equal(h.pe("generate").disabled, true); assert.equal(h.pe("prepare").disabled, true);
  assert.match(h.pe("status").textContent, /Commande locale : a{32}/);
  h.pe("form").dispatchEvent(new h.ctx.Event("submit")); await flush();
  assert.equal(wire.calls.length, 1, "Uncertain state prevents replay");
});
test("context editing during bounded preparation still invalidates the later result", async () => {
  const {h, wire} = preparation(); let finish;
  wire.ctx.reply = (route, options) => new Promise(resolve => {finish = () => resolve(response({
    context: JSON.parse(options.body).context, references: []}));});
  h.pe("form").dispatchEvent(new h.ctx.Event("submit")); await flush();
  h.pe("level").value = "BTS_CG_YEAR_1"; h.pe("form").dispatchEvent(new h.ctx.Event("input"));
  wire.advance(16859); finish(); await flush();
  assert.equal(h.ctx.p0.prepared, null); assert.equal(h.pe("level").value, "BTS_CG_YEAR_1");
  assert.equal(wire.calls.length, 1);
});
