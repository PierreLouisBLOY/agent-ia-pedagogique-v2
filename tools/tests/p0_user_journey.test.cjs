'use strict';
// Exercises the shared workflow guide against exact version identities. No browser,
// Application, provider, database, or saved-store authority is supplied.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');

const source = fs.readFileSync('frontend/app.js', 'utf8');
const html = fs.readFileSync('frontend/index.html', 'utf8');
const start = source.indexOf('function p0WorkflowKey(');
const end = source.indexOf('async function p0Fetch(', start);
assert(start >= 0 && end > start, 'workflow functions stay in the active P0 path');

class Node {
  constructor() { this.dataset = {}; this.attributes = {}; this.textContent = ''; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
}
function harness(view = null) {
  const nodes = new Map();
  const p0 = {view, dirty:false, workflowAudit:null, workflowSaved:null};
  const document = {getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, new Node());
    return nodes.get(id);
  }};
  const ctx = {p0, document};
  vm.createContext(ctx);
  vm.runInContext(source.slice(start, end), ctx);
  return {ctx, nodes};
}
function view(version, family='COURSE') {
  return {production_ref:'prod:' + 'a'.repeat(32), version_ref:'ver:' + version.repeat(32),
    bundle_sha256:version.repeat(64), references:[{ref:'local:one'}],
    pedagogical_context:{resource_type:family}};
}
const key = value => [value.production_ref, value.version_ref, value.bundle_sha256].join('/');

test('guide starts at context and references without suggesting authority or provider action', () => {
  const h = harness(); h.ctx.p0Workflow();
  assert.equal(h.nodes.get('p0-step-context').dataset.state, 'current');
  assert.match(h.nodes.get('p0-step-context-status').textContent, /niveau, les objectifs et les références/);
  assert.equal(h.nodes.get('p0-step-export').dataset.state, 'pending');
  assert.match(html, /La recette enseignante reste distincte/);
  assert.match(html, /Confirmer le contexte et les références/);
});

for (const family of ['COURSE', 'EXERCISE', 'ASSESSMENT', 'QCM', 'QUIZ', 'OPEN_QUESTIONS']) {
  test(`shared guide binds audit, save and export for ${family}`, () => {
    const selected = view('2', family); const h = harness(selected);
    h.ctx.p0Workflow();
    assert.equal(h.nodes.get('p0-step-context').dataset.state, 'done');
    assert.match(h.nodes.get('p0-step-context-status').textContent, /1 référence.*ne vaut pas admission/);
    assert.equal(h.nodes.get('p0-step-audit').dataset.state, 'current');

    h.ctx.p0.workflowAudit = {key:key(selected), status:'PASS'};
    h.ctx.p0Workflow();
    assert.equal(h.nodes.get('p0-step-audit').dataset.state, 'done');
    assert.equal(h.nodes.get('p0-step-save').dataset.state, 'current');
    assert.match(h.nodes.get('p0-step-audit-status').textContent, /pas une validation pédagogique/);

    h.ctx.p0.workflowSaved = key(selected);
    h.ctx.p0Workflow();
    assert.equal(h.nodes.get('p0-step-save').dataset.state, 'done');
    assert.equal(h.nodes.get('p0-step-export').dataset.state, 'current');
  });
}

test('a failed audit or local edits return the guide to refinement and never inherit another version proof', () => {
  const original = view('3'); const h = harness(original);
  h.ctx.p0.workflowAudit = {key:key(original), status:'FAIL'};
  h.ctx.p0.workflowSaved = key(original);
  h.ctx.p0Workflow();
  assert.equal(h.nodes.get('p0-step-audit').dataset.state, 'attention');
  assert.equal(h.nodes.get('p0-step-review').attributes['aria-current'], 'step');

  h.ctx.p0.dirty = true; h.ctx.p0Workflow();
  assert.equal(h.nodes.get('p0-step-review').dataset.state, 'attention');
  assert.match(h.nodes.get('p0-step-audit-status').textContent, /créez une nouvelle version/);
  assert.equal(h.nodes.get('p0-step-save').dataset.state, 'current');

  h.ctx.p0.dirty = false; h.ctx.p0.view = view('4'); h.ctx.p0Workflow();
  assert.equal(h.nodes.get('p0-step-audit').dataset.state, 'current');
  assert.equal(h.nodes.get('p0-step-save').dataset.state, 'current');
  assert.equal(h.nodes.get('p0-step-export').dataset.state, 'pending');
});

test('save-and-reopen marks only the exact version after Application returns', async () => {
  const selected = view('5'); const h = harness(selected); const calls = [];
  const from = source.indexOf('async function p0SaveVersion()');
  const to = source.indexOf('p0Element("save").addEventListener', from);
  assert(from >= 0 && to > from, 'save handler stays on the existing P0 lifecycle');
  h.ctx.r4Versions = {value:''};
  h.ctx.r4Fetch = async (path, body) => { calls.push({path, body}); };
  h.ctx.r4Refresh = async () => {};
  h.ctx.r4Open = async () => { assert.equal(h.ctx.r4Versions.value, selected.production_ref + '/' + selected.version_ref); };
  h.ctx.p0Element = id => h.nodes.get(id) || (h.nodes.set(id, new Node()), h.nodes.get(id));
  h.ctx.p0.workflowAudit = {key:key(selected), status:'PASS'};
  vm.runInContext(source.slice(from, to), h.ctx);
  await h.ctx.p0SaveVersion();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/v2/conversation/saved');
  assert.equal(calls[0].body.production_ref, selected.production_ref);
  assert.equal(calls[0].body.version_ref, selected.version_ref);
  assert.equal(h.ctx.p0.workflowSaved, key(selected));
  assert.equal(h.nodes.get('p0-step-export').dataset.state, 'current');
  assert.match(h.nodes.get('status').textContent, /Version exacte sauvegardée et rouverte/);
});

test('an incomplete reopen does not mark the workflow as saved', async () => {
  const selected = view('6'); const h = harness(selected);
  const from = source.indexOf('async function p0SaveVersion()');
  const to = source.indexOf('p0Element("save").addEventListener', from);
  h.ctx.r4Versions = {value:''};
  h.ctx.r4Fetch = async () => {};
  h.ctx.r4Refresh = async () => {};
  h.ctx.r4Open = async () => { throw new Error('R4_REOPEN_FAILED'); };
  h.ctx.p0Element = id => h.nodes.get(id) || (h.nodes.set(id, new Node()), h.nodes.get(id));
  vm.runInContext(source.slice(from, to), h.ctx);
  await assert.rejects(h.ctx.p0SaveVersion(), /R4_REOPEN_FAILED/);
  assert.equal(h.ctx.p0.workflowSaved, null);
});
