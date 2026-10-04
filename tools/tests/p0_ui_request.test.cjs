// Execute the actual transport helper against stalled headers and stalled bodies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const helper = source.slice(source.indexOf('async function localBoundedRequest('), source.indexOf('async function conversationFetch('));
const preview = source.slice(source.indexOf('function classroomPreview('), source.indexOf('document.getElementById("r4-preview").addEventListener'));
function checkPreview() {
  const node = tag => ({tag, children:[], append(...items) {this.children.push(...items);},
    set textContent(value) {this.children=[String(value)];}});
  const context = {document:{createElement:node,createTextNode:value=>String(value)}};
  vm.createContext(context); vm.runInContext(preview, context);
  const output = node('article');
  context.classroomPreview(output,[{style:'Heading1',text:'Dossier 1'},
    {style:'Normal',text:'## Dossier 1 — Données\n\n**300,0 €** et valeur_brute * 2 ; <img src=x onerror=alert(1)>\n| Poste | Montant |\n| --- | ---: |\n| Stock | 300 |'},
    {style:'Heading2',text:'Q01'},{style:'Normal',text:'**1. Calculer.**'},
    {style:'Note',text:'Version exacte : ver:'+'a'.repeat(32)}]);
  const flatten = item => typeof item==='string' ? item : item.children.map(flatten).join('');
  const text = flatten(output);
  assert.match(text,/300,0 €.*valeur_brute \* 2/);
  assert.match(text,/<img src=x onerror=alert\(1\)>/,'Untrusted HTML stays text');
  assert.equal(output.children.filter(item=>item.tag==='table').length,1);
  assert.equal(output.children.filter(item=>item.tag==='h4').length,1,'No duplicated section heading');
  assert.doesNotMatch(text,/Q01|ver:|\*\*|\| ---/);
  assert.equal(text.includes('Stock300'),true);
}

async function check(mode) {
  let calls = 0, deadline;
  const pending = signal => new Promise((resolve, reject) => {
    if (signal.aborted) reject(new Error('ABORTED'));
    else signal.addEventListener('abort', () => reject(new Error('ABORTED')));
  });
  const context = {AbortController, setTimeout: callback => {deadline = callback; return 1;}, clearTimeout: () => {},
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, '/local'); assert.equal(options.method, 'POST');
      if (mode === 'headers') return pending(options.signal);
      return {json: () => mode === 'body' ? pending(options.signal) : Promise.resolve({state:'OK'})};
    }};
  vm.createContext(context); vm.runInContext(helper, context);
  const result = context.localBoundedRequest('/local', {method:'POST'}, response => response.json());
  await Promise.resolve(); await Promise.resolve();
  if (mode === 'success') assert.equal((await result).state, 'OK');
  else {deadline(); await assert.rejects(result, /ABORTED/);}
  assert.equal(calls, 1, 'A stalled command must never retry automatically');
}
(async () => {for (const mode of ['success','headers','body']) await check(mode); checkPreview(); console.log('3 transport checks and classroom preview PASS');})().catch(error => {console.error(error); process.exitCode=1;});
