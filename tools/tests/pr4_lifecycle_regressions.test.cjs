'use strict';
// Real source handlers. DOM, HTTP, context preview and layout are explicit doubles.
// No provider, SQL, browser engine or application authority is supplied by this VM.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), {test} = require('node:test');
const source = fs.readFileSync(path.resolve(__dirname, '../../frontend/app.js'), 'utf8');
const between = (a, b) => {
  const start = source.indexOf(a), end = source.indexOf(b, start + 1);
  assert(start >= 0 && end > start, a); return source.slice(start, end);
};
const code = [
  between('function p0Controls()', 'async function p0Fetch('),
  between('async function p0Run(', 'const p0Command'),
  between('function p0Context()', 'function p0Field('),
  between('function p0Field(', 'p0Element("teacher").addEventListener'),
  between('p0Element("revise").addEventListener', 'async function p0SaveVersion()'),
  between('async function proposePreparation(text)', 'function uxContext('),
  between('function uxQuality(', 'function uxPreparation('),
  between('function uxProductionCard(', 'async function uxTeacherCard('),
  between('function uxSavedCard(', 'document.querySelectorAll("[data-view]")'),
  between('document.getElementById("preparation-composer").addEventListener', 'document.getElementById("card-open").addEventListener')
].join('\n');
function harness() {
  const nodes = new Map(), messages = [], calls = [], contexts = [];
  class Node {
    constructor(id = '') {this._id = id; this.value = ''; this.children = []; this.listeners = {}; this.selectedOptions = []; this.dataset = {}; this._text = '';}
    set id(v) {this._id = v; nodes.set(v, this);} get id() {return this._id;}
    set textContent(v) {this._text = String(v); this.children = [];}
    get textContent() {return this._text + this.children.map(n => typeof n === 'string' ? n : n.textContent).join('');}
    replaceChildren(...children) {this.children = children; this._text = ''; this.value = ''; this.selectedOptions = [];}
    append(...children) {this.children.push(...children);}
    addEventListener(type, handler) {(this.listeners[type] ??= []).push(handler);}
    dispatchEvent(e) {return (this.listeners[e.type] || []).map(f => f(e));}
    focus() {} setAttribute() {} scrollIntoView() {}
  }
  const node = id => {if (!nodes.has(id)) nodes.set(id, new Node(id)); return nodes.get(id);}, pe = id => node('p0-' + id);
  const ctx = {p0: {busy:false, uncertain:false, references:[], institutionalCatalog:{frames:[], bts_frameworks:[], notions:[]}},
    document:{getElementById:node, createElement:() => new Node()}, p0Element:pe,
    Event:class {constructor(type) {this.type=type;} preventDefault() {}}, uxRequests:[],
    uxMessage:(role,text) => messages.push({role,text}), uxShow:() => {}, uxDraftConfirm:()=>true, uxContext:c => contexts.push(c),
    uxPreparation:p => {contexts.push(p.context); ctx.uxQuality(p.agentic?.quality, null);},
    appendSearchText:(parent,tag,text) => {const n = new Node(); n.textContent=text; parent.append(n);},
    uxNames:{EXERCISE:'Exercice', BTS_CG_YEAR_2:'BTS CG deuxième année', FIRST_STMG:'Première STMG'},
    classroomPreview:(parent,blocks) => {for(const b of blocks) {const n=new Node(); n.textContent=b.text; parent.append(n);}},
    p0Command:() => 'a'.repeat(32), p0Fetch:async (...args) => {calls.push(args);
      if(args[0]==='/api/v2/p0/intention')return {contract_id:"P0-INTENTION-PROPOSAL-1.0",
        command_id:args[1].command_id,confirmation_required:true,provider_attempts:0,
        implementation:"DETERMINISTIC_APPLICATION_PROPOSAL",authority:"NONE",state:"CONTEXT_PROPOSED",
        proposal:ctx.proposal||{},missing_fields:[],ambiguities:[]};
      return ctx.transport ? ctx.transport(...args) : ctx.nextResponse;}, console};
  ctx.p0.institutionalCatalog.bts_frameworks = [{program_ref:'bts:test', program_version:'version:test', label:'BTS CG synthétique', version_label:'TEST',
    elements:[{id:'process:test', element_type:'PROCESS', parent_ref:null},
      {id:'activity:test', element_type:'ACTIVITY', parent_ref:'process:test', official_code:'TEST', official_label:'Activité synthétique'},
      {id:'competency:test', element_type:'COMPETENCY', parent_ref:'activity:test', official_label:'Compétence synthétique'}]}];
  ctx.p0.institutionalCatalog.notions = [{notion_ref:'notion:test', label:'Notion synthétique'}];
  vm.createContext(ctx); vm.runInContext(code, ctx); return {ctx,node,pe,messages,calls,contexts};
}
function select(h) {
  h.pe('frame').value='version:test'; h.pe('frame').dispatchEvent(new h.ctx.Event('change'));
  h.pe('program-question').value='activity:test'; h.pe('program-question').dispatchEvent(new h.ctx.Event('change'));
  h.pe('capacities').selectedOptions=[{value:'competency:test'}]; h.pe('program-notions').selectedOptions=[{value:'notion:test'}]; h.pe('depth').value='APPLICATION';
}
for(const year of ['1','2']) for(const preset of [false,true]) test(`BTS CG${year} submit, preset=${preset}, clarification before confirmation`, async () => {
  const h=harness(); h.pe('level').value='BTS_CG_YEAR_2'; h.ctx.p0InstitutionalOptions(); if(preset) select(h);
  h.ctx.proposal={family:'EXERCISE',level:'BTS_CG_YEAR_'+year,difficulty:'STANDARD',
    topics:['Effectifs'],objectives:['Justifier la méthode'],duration_minutes:null,total_points:null};
  h.node('preparation-prompt').value=`Un exercice BTS CG ${year} sur les effectifs.`;
  assert.doesNotThrow(() => h.node('preparation-composer').dispatchEvent(new h.ctx.Event('submit')));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.pe('frame').value,''); assert.equal(h.calls.length,1); assert.equal(h.calls[0][0],'/api/v2/p0/intention'); assert.equal(h.node('preparation-parameters').open,true);
  assert(h.messages.some(m => m.role === 'assistant' && /référentiel/.test(m.text) && /activité/.test(m.text)));
  assert.equal(h.node('preparation-prompt').value,'');
  assert.throws(() => h.ctx.p0Context(), /CONTEXT_REQUIRED/);
  select(h);
  h.pe('notion-id').value='notion:test'; h.pe('search-passage').value='synthetic:canonical';
  h.ctx.transport=async (route,body) => ({context:body.context, references:[], preparation_ref:'prepared:test', preparation_sha256:'a'.repeat(64)});
  h.pe('form').dispatchEvent(new h.ctx.Event('submit'));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls.length,2); assert.equal(h.calls[1][0],'/api/v2/p0/prepare');
  const selection=h.calls[1][1].context.institutional;
  assert.equal(selection.program_ref,'bts:test'); assert.equal(selection.process_ref,'process:test'); assert.equal(selection.activity_ref,'activity:test');
  assert.deepEqual(Array.from(selection.competency_refs),['competency:test']);
  assert.equal(selection.local_year,'BTS_CG_YEAR_'+year); assert.equal(h.ctx.p0.uncertain,false);
});
for(const prompt of ['Un cours première STMG sur les organisations.', 'Prépare un document sur les organisations.']) test('composer witness: '+prompt, async () => {
  const h=harness(); h.ctx.proposal={family:prompt.startsWith('Un cours')?'COURSE':null,
    level:prompt.startsWith('Un cours')?'FIRST_STMG':null,difficulty:null,topics:['Organisations'],
    objectives:[],duration_minutes:null,total_points:null}; h.node('preparation-prompt').value=prompt;
  assert.doesNotThrow(() => h.node('preparation-composer').dispatchEvent(new h.ctx.Event('submit')));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(h.calls.length,1); assert.equal(h.calls[0][0],'/api/v2/p0/intention'); assert.equal(h.node('preparation-parameters').open,true);
  assert(h.messages.some(m => m.role === 'assistant')); assert.equal(h.node('preparation-prompt').value,'');
});
function view(digit='2') {return {production_ref:'prod:'+'1'.repeat(32), version_ref:'ver:'+digit.repeat(32), bundle_sha256:digit.repeat(64), title:'Test synthétique',
  pedagogical_context:{resource_type:'EXERCISE',level:'BTS_CG_YEAR_2',objectives:['Présenter les acteurs']}, references:[], sections:[{section_id:'S01',heading:'Situation',text:'Une association.'}],
  questions:[{question_id:'Q01',prompt:'Présentez les acteurs.',options:[]}]};}
const parentQuality={sources:'SOURCES_OK',calculations:'NON_APPLICABLE',instruction:'CONSIGNE_COUVERTE',review:'REVUE_OK',human_review:'HUMAN_REVIEW_REQUIRED'};
const childQuality={...parentQuality,calculations:'ECHEC',instruction:'PARTIELLE',review:'RESERVE'};
function parent(h) {h.ctx.p0Render(view()); h.ctx.uxQuality(parentQuality); assert(h.node('drawer-quality').textContent.includes('Aucun calcul requis'));}
for(const quality of [childQuality,undefined]) test('revision replaces parent quality: '+(quality ? 'provided':'missing'), async () => {
  const h=harness(); parent(h); const child=view('3'); child.questions[0].prompt='Combien de salariés supplémentaires ?';
  h.ctx.nextResponse={state:'CANDIDATE',view:child,quality}; await h.pe('revise').listeners.click[0]();
  assert.equal(h.ctx.p0.view.version_ref,child.version_ref); const text=h.node('drawer-quality').textContent;
  assert(!text.includes('Aucun calcul requis')); assert(!text.includes('Revue technique sans réserve'));
  assert(text.includes(quality ? 'Preuve indépendante des calculs manquante':'Non vérifié'));
  assert.equal(h.node('drawer-quality').dataset.versionRef,child.version_ref);
});
test('generation keeps the quality returned for the new version', async () => {
  const h=harness(); parent(h); h.ctx.p0.prepared={preparation_ref:'prepared:test',preparation_sha256:'a'.repeat(64)};
  h.ctx.nextResponse={state:'CANDIDATE',view:view('3'),agentic:{quality:childQuality}};
  await h.pe('generate').listeners.click[0](); assert(h.node('drawer-quality').textContent.includes('Preuve indépendante des calculs manquante'));
  assert.equal(h.node('drawer-quality').dataset.versionRef,view('3').version_ref);
});
test('validation is displayed for its current version', async () => {
  const h=harness(); parent(h); h.ctx.nextResponse={status:'PASS',quality:childQuality};
  await h.pe('validate').listeners.click[0](); assert(h.node('drawer-quality').textContent.includes('Preuve indépendante des calculs manquante'));
  assert.equal(h.calls[0][1].version_ref,view().version_ref);
});
for(const reopen of [false,true]) test('late validation cannot overwrite '+(reopen?'reopened':'revised')+' version', async () => {
  const h=harness(); parent(h); let resolve;
  h.ctx.transport=() => new Promise(r => {resolve=r;}); const pending=h.pe('validate').listeners.click[0]();
  if(reopen) h.ctx.uxSavedCard({record:{view:view('3'),reviews:[],validations:[],provenance:{}},record_sha256:'f'.repeat(64)});
  else h.ctx.p0Render(view('3'));
  resolve({status:'PASS',quality:parentQuality}); await pending;
  assert(!h.node('drawer-quality').textContent.includes('Revue technique sans réserve'));
  assert.equal(h.node('drawer-quality').dataset.versionRef,view('3').version_ref);
});
test('reopening does not inherit parent claims or attest preserved reports', () => {
  const h=harness(); parent(h); h.ctx.uxSavedCard({record:{view:view('3'),reviews:[{version_ref:view().version_ref}],validations:[],provenance:{}},record_sha256:'f'.repeat(64)});
  assert(!h.node('drawer-quality').textContent.includes('Aucun calcul requis'));
  assert(h.node('drawer-quality').textContent.includes('Non vérifié'));
  assert.equal(h.node('drawer-quality').dataset.versionRef,view('3').version_ref);
});
