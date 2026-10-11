"use strict";
// Separate review pass: reuse the explicit DOM/transport fixture, execute the shipped handlers.
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const assert=require("node:assert/strict"),{test}=require("node:test");
const fixture=fs.readFileSync(path.join(__dirname,"pr4_lifecycle_regressions.test.cjs"),"utf8");
const ctx={require,__dirname,console};
vm.createContext(ctx);vm.runInContext(fixture.slice(0,fixture.indexOf("for(const year")),ctx);
function preparedHarness(){const h=ctx.harness();
  h.ctx.p0.contextRevision=0;
  h.pe("level").value="BTS_CG_YEAR_2";h.ctx.p0InstitutionalOptions();ctx.select(h);
  h.pe("notion-id").value="notion:test";h.pe("search-passage").value="synthetic:canonical";return h;}
test("editing a context during preparation invalidates its late response",async()=>{
  const h=preparedHarness();let resolve;
  h.ctx.transport=(route,body)=>new Promise(done=>{resolve=()=>done({context:body.context,references:[],
    preparation_ref:"prep:"+"a".repeat(32),preparation_sha256:"b".repeat(64)});});
  const pending=h.pe("form").dispatchEvent(new h.ctx.Event("submit"))[0];
  assert.equal(h.ctx.p0.busy,true);
  h.pe("level").value="BTS_CG_YEAR_1";h.pe("form").dispatchEvent(new h.ctx.Event("input"));
  assert.equal(h.ctx.p0.prepared,null);resolve();await pending;
  await new Promise(done=>setImmediate(done));
  assert.equal(h.ctx.p0.prepared,null,"A changed form must not regain consent/generation for its old context");
  assert.equal(h.pe("generate").disabled,true);
});
test("an unchanged context still accepts its one preparation response",async()=>{
  const h=preparedHarness();
  h.ctx.transport=async(route,body)=>({context:body.context,references:[],
    preparation_ref:"prep:"+"a".repeat(32),preparation_sha256:"b".repeat(64)});
  h.pe("form").dispatchEvent(new h.ctx.Event("submit"));await new Promise(done=>setImmediate(done));
  assert.equal(h.ctx.p0.prepared.context.level,"BTS_CG_YEAR_2");
  assert.equal(h.calls.length,1);assert.equal(h.ctx.p0.uncertain,false);
});
test("reconsulting a teacher companion preserves its uncommitted edit",async()=>{
  const h=ctx.harness(),source=fs.readFileSync(path.join(__dirname,"../../frontend/app.js"),"utf8");
  vm.runInContext(source.slice(source.indexOf('p0Element("teacher").addEventListener'),
    source.indexOf('p0Element("revise").addEventListener')),h.ctx);
  const view={production_ref:"prod:"+"1".repeat(32),version_ref:"ver:"+"2".repeat(32),bundle_sha256:"2".repeat(64),
    title:"SYNTHETIC",pedagogical_context:{resource_type:"EXERCISE",level:"BTS_CG_YEAR_2",objectives:[]},references:[],
    sections:[{section_id:"S1",heading:"Situation",text:"DONNEES SYNTHETIQUES"}],
    questions:[{question_id:"Q1",prompt:"Calculer",options:[]}]};
  h.ctx.p0Render(view);
  h.ctx.nextResponse={production_ref:view.production_ref,version_ref:view.version_ref,bundle_sha256:view.bundle_sha256,
    corrections:[{question_id:"Q1",expected_answer:"REPONSE CONSERVEE",rationale:"Explication"}],marking:[]};
  await h.pe("teacher").listeners.click[0]();
  h.node("p0-edit-answer-0").value="MODIFICATION NON CONSERVEE";h.ctx.p0.dirty=true;h.ctx.p0Controls();
  if(!h.pe("teacher").disabled)await h.pe("teacher").listeners.click[0]();
  assert.equal(h.node("p0-edit-answer-0").value,"MODIFICATION NON CONSERVEE",
    "Readonly reconsultation must not silently overwrite an uncommitted teacher edit");
  assert.equal(h.ctx.p0.dirty,true);
});
test("an edit made during a pending revision is not silently overwritten by its child response",async()=>{
  const h=ctx.harness(),source=fs.readFileSync(path.join(__dirname,"../../frontend/app.js"),"utf8");
  const start=source.indexOf('function p0Edited(');
  vm.runInContext(source.slice(start,source.indexOf('window.addEventListener("beforeunload"',start)),h.ctx);
  const view={production_ref:"prod:"+"1".repeat(32),version_ref:"ver:"+"2".repeat(32),bundle_sha256:"2".repeat(64),
    title:"SYNTHETIC",pedagogical_context:{resource_type:"EXERCISE",level:"BTS_CG_YEAR_2",objectives:[]},references:[],
    sections:[{section_id:"S1",heading:"Situation",text:"DONNEES SYNTHETIQUES"}],
    questions:[{question_id:"Q1",prompt:"Calculer",options:[]}]};
  h.ctx.p0Render(view);h.node("p0-edit-title").value="PREMIERE EDITION";
  h.node("production-edit-panel").dispatchEvent(new h.ctx.Event("input"));
  let resolve;h.ctx.transport=(route,body)=>new Promise(done=>{resolve=()=>done({state:"CANDIDATE",
    view:{...view,title:body.edits.title,version_ref:"ver:"+"3".repeat(32),bundle_sha256:"3".repeat(64)}});});
  const pending=h.pe("revise").listeners.click[0]();assert.equal(h.ctx.p0.busy,true);
  const edit=h.node("p0-edit-title");
  if(!edit.disabled&&!edit.readOnly){edit.value="EDITION PENDANT LA REQUETE";
    h.node("production-edit-panel").dispatchEvent(new h.ctx.Event("input"));}
  resolve();await pending;
  if(edit.value==="EDITION PENDANT LA REQUETE"){
    assert.equal(h.node("p0-edit-title").value,"EDITION PENDANT LA REQUETE");assert.equal(h.ctx.p0.dirty,true);
  }else assert.equal(h.ctx.p0.view.title,"PREMIERE EDITION","The received child must not discard a newer editable draft");
});
function sourceHarness(){const h=preparedHarness();h.ctx.p0.prepared=null;h.pe("source-notion").value="notion:test";
  h.pe("source-notion").selectedOptions=[{value:"notion:test",textContent:"Notion synthétique"}];
  h.pe("notion-id").value="";h.pe("search-passage").value="";
  h.ctx.nextResponse={notion_id:"notion:test",available_authority:"UNKNOWN",exclusions:[],items:[{
    object_ref:"notion:test",object_kind:"NOTION",passage_ref:"synthetic:passage",version_or_checksum:"VERSION_SYNTHETIQUE",
    excerpt:"EXTRAIT SYNTHETIQUE",excerpt_sha256:"a".repeat(64),excerpt_truncated:false,
    provenance:{type:"SYNTHETIC"},source_status:"ACTIVE",selection:{notion_id:"notion:test",passage_ref:"synthetic:passage"}}]};
  return h;}
test("source picker carries the exact passage/version/provenance while authority remains UNKNOWN",async()=>{
  const h=sourceHarness();await h.pe("source-load").listeners.click[0]();
  assert.equal(h.calls.length,1);assert.equal(h.calls[0][0],"/api/v2/p0/notion-evidence?notion_id=notion%3Atest");
  assert(h.pe("source-choices").textContent.includes("VERSION_SYNTHETIQUE"));
  assert(h.pe("source-choices").textContent.includes('"authority": "UNKNOWN"'));
  const button=h.pe("source-choices").children.at(-1).children.at(-1);button.listeners.click[0]();
  assert.equal(h.pe("notion-id").value,"notion:test");assert.equal(h.pe("search-passage").value,"synthetic:passage");
  assert.equal(h.ctx.p0.prepared,null);assert.equal(h.calls.length,1,"Selecting is not provider dispatch or admission");
});
test("a late source response cannot publish after the context has changed",async()=>{
  const h=sourceHarness();let resolve;h.ctx.transport=()=>new Promise(done=>{resolve=()=>done(h.ctx.nextResponse);});
  const pending=h.pe("source-load").listeners.click[0]();h.ctx.p0Invalidate();resolve();await pending;
  assert.equal(h.pe("source-choices").children.length,0);assert.equal(h.pe("notion-id").value,"");
  assert.match(h.pe("status").textContent,/P0_NOTION_SOURCE_RESPONSE_BINDING/);assert.equal(h.calls.length,1);
});
test("a displayed source button cannot select its passage after a context change even when notion label stays the same",async()=>{
  const h=sourceHarness();await h.pe("source-load").listeners.click[0]();
  const button=h.pe("source-choices").children.at(-1).children.at(-1);h.ctx.p0Invalidate();button.listeners.click[0]();
  assert.equal(h.pe("notion-id").value,"");assert.equal(h.pe("search-passage").value,"");assert.equal(h.calls.length,1);
});
test("an invalid second source item cannot leave a selectable partial first result",async()=>{
  for(const mutation of ["RESOURCE","INCOMPLETE"]){
    const h=sourceHarness(),item=structuredClone(h.ctx.nextResponse.items[0]);
    if(mutation==="RESOURCE")item.object_kind="RESOURCE";else item.excerpt="";
    h.ctx.nextResponse.items.push(item);await h.pe("source-load").listeners.click[0]();
    assert.equal(h.pe("source-choices").children.length,0,"Validate the complete response before publishing any button");
    assert.equal(h.pe("notion-id").value,"");assert.equal(h.pe("search-passage").value,"");
    assert.match(h.pe("status").textContent,/P0_NOTION_SOURCE_RESPONSE_BINDING/);assert.equal(h.calls.length,1);
  }
});
test("a new intention clears the reopened production context, sources and quality without inheriting its claims",async()=>{
  const h=ctx.harness();h.ctx.p0.contextRevision=0;
  const old={production_ref:"prod:"+"1".repeat(32),version_ref:"ver:"+"2".repeat(32),bundle_sha256:"2".repeat(64),
    sections:[],questions:[],pedagogical_context:{resource_type:"COURSE"}};
  h.ctx.p0.view=old;h.ctx.p0.teacher={old:true};h.ctx.p0.prepared={preparation_ref:"prep:ancienne"};
  h.node("drawer-context").textContent="M01 CONTEXTE STMG";h.node("drawer-sources").textContent="M01 SOURCES CONSERVEES";
  h.node("drawer-identities").textContent=JSON.stringify(old);
  h.ctx.uxQuality({sources:"SOURCES_OK",calculations:"CALCULS_VERIFIES",instruction:"CONSIGNE_COUVERTE",review:"REVUE_OK"},old);
  h.ctx.proposal={family:"EXERCISE",level:"BTS_CG_YEAR_2",difficulty:"STANDARD",topics:["BFR"],
    objectives:["Interpréter le BFR"],duration_minutes:null,total_points:null};
  h.node("preparation-prompt").value="Un exercice BTS CG deuxième année sur le BFR";
  h.node("preparation-composer").dispatchEvent(new h.ctx.Event("submit"));await new Promise(done=>setImmediate(done));
  assert.equal(h.ctx.p0.view,null);assert.equal(h.ctx.p0.teacher,null);assert.equal(h.ctx.p0.prepared,null);
  assert.equal(h.node("production-card").hidden,true);
  assert.doesNotMatch(h.node("drawer-context").textContent,/M01|STMG/);
  assert.match(h.node("drawer-context").textContent,/contexte à confirmer/);
  assert.match(h.node("drawer-sources").textContent,/Aucune source confirmée/);assert.equal(h.node("drawer-identities").textContent,"");
  assert.match(h.node("drawer-quality").textContent,/Non vérifié/);
  assert.doesNotMatch(h.node("drawer-quality").textContent,/Identité des sources contrôlée|Calculs vérifiés|Revue technique sans réserve/);
  for(const key of ["productionRef","versionRef","bundleSha256"])assert.equal(h.node("drawer-quality").dataset[key],"");
  assert.equal(h.calls.length,1);assert.equal(h.calls[0][0],"/api/v2/p0/intention");
});
test("BTS source selection admits the exact canonical notion and keeps content, method and notion aliases consultable only",async()=>{
  for(const kind of ["CANONICAL","PEDAGOGICAL_CONTENT","METHOD","ALIAS"]){
    const h=sourceHarness(),item=h.ctx.nextResponse.items[0];
    if(kind==="ALIAS")item.object_ref="notion:other-exact-object";
    else if(kind!=="CANONICAL")item.object_kind=kind;
    await h.pe("source-load").listeners.click[0]();
    const article=h.pe("source-choices").children.at(-1),button=article.children.at(-1);
    assert(article.textContent.includes("EXTRAIT SYNTHETIQUE"),"Ineligible source stays readable with provenance");
    assert.equal(button.disabled,kind!=="CANONICAL");
    if(kind!=="CANONICAL")assert.match(article.textContent,/Passage consultable.*n’est pas admise/);
    button.listeners.click[0](); // Deliberate forced handler call: disabled DOM alone is insufficient.
    assert.equal(h.pe("notion-id").value,kind==="CANONICAL"?"notion:test":"");
    assert.equal(h.pe("search-passage").value,kind==="CANONICAL"?"synthetic:passage":"");
    assert.equal(h.calls.length,1);assert.equal(h.ctx.p0.prepared,null);
  }
});
test("rechoosing a passage in the same context clears preparation and consent without provider dispatch",async()=>{
  const h=sourceHarness(),second=structuredClone(h.ctx.nextResponse.items[0]);
  second.passage_ref="synthetic:second-passage";second.selection.passage_ref=second.passage_ref;
  second.excerpt="SECOND EXTRAIT SYNTHETIQUE";h.ctx.nextResponse.items.push(second);
  await h.pe("source-load").listeners.click[0]();
  const articles=h.pe("source-choices").children.slice(1),buttons=articles.map(article=>article.children.at(-1));
  const revision=h.ctx.p0.contextRevision;
  for(const [index,button] of buttons.entries()){
    h.ctx.p0.prepared={preparation_ref:"prep:ancienne"};h.ctx.p0.consent={ancienne:true};
    button.listeners.click[0]();
    assert.equal(h.pe("search-passage").value,index===0?"synthetic:passage":"synthetic:second-passage");
    assert.equal(h.ctx.p0.prepared,null);assert.equal(h.ctx.p0.consent,null);
    assert.equal(h.ctx.p0.contextRevision,revision,"Source choice must not invalidate the unchanged context");
  }
  assert.equal(h.calls.length,1);assert.match(h.calls[0][0],/notion-evidence/);
  h.ctx.p0Invalidate();buttons[0].listeners.click[0]();
  assert.equal(h.pe("search-passage").value,"synthetic:second-passage","A real context change still makes old buttons stale");
});
