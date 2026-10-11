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

// The next tests execute the proposed source verbatim. DOM, HTTP and deadlines
// are explicit doubles. No browser engine, server, SQL or provider is invoked.
const proposedSource=fs.readFileSync(path.join(__dirname,"../../frontend/app.js"),"utf8");
const fragment=(start,end)=>{const a=proposedSource.indexOf(start),b=proposedSource.indexOf(end,a+1);
  assert(a>=0&&b>a,start);return proposedSource.slice(a,b);};
const flush=()=>new Promise(done=>setImmediate(done));
const syntheticView=()=>({production_ref:"prod:"+"1".repeat(32),version_ref:"ver:"+"2".repeat(32),
  bundle_sha256:"2".repeat(64),title:"SYNTHETIC LOCAL DOCUMENT",
  pedagogical_context:{resource_type:"EXERCISE",level:"BTS_CG_YEAR_2",objectives:[]},references:[],
  sections:[{section_id:"S1",heading:"Situation",text:"DONNEES SYNTHETIQUES"}],questions:[]});
const syntheticMetadata=()=>({state:"READY",authority:"NONE",transport_nonce:"N".repeat(43),references:[],
  live_binding:"NONE",normal_consent_binding:"NONE",media_binding:"NONE",
  institutional_catalog:{frames:[],bts_frameworks:[],notions:[]}});
const envelope=data=>({ok:true,status:200,json:async()=>({meta:{contract_id:"R6-P0-HTTP-LOCAL-1.0"},data})});
function connectionHarness(metadataHandler){
  const h=ctx.harness(),network=[],deadlines=new Map();let serial=0;
  Object.assign(h.ctx.p0,{nonce:null,connected:false,liveBinding:"NONE",normalConsentBinding:"NONE",mediaBinding:"NONE"});
  Object.assign(h.ctx,{AbortController,setTimeout:(fn,ms)=>{const id=++serial;deadlines.set(id,{fn,ms});return id;},
    clearTimeout:id=>deadlines.delete(id),r4Record:{record:{origin:"LOCAL_APPLICATION",view:syntheticView()}},
    r4ResumePending:false,r4Status:h.node("r4-status"),r4Controls:()=>{
      h.node("r4-resume").disabled=h.ctx.r4ResumePending;},fetch:async(route,options)=>{
      network.push({route,options});
      if(route==="/api/v2/p0")return metadataHandler?metadataHandler(route,options):envelope(syntheticMetadata());
      if(route.startsWith("/api/v2/p0/versions/"))return envelope(syntheticView());
      if(route==="/api/v2/p0/revise"){
        const body=JSON.parse(options.body);return envelope({state:"CANDIDATE",view:{...syntheticView(),
          title:body.edits.title,version_ref:"ver:"+"3".repeat(32),bundle_sha256:"3".repeat(64)}});}
      throw new Error("UNEXPECTED_SYNTHETIC_ROUTE:"+route);
    }});
  vm.runInContext(fragment("async function localBoundedRequest(","async function conversationFetch("),h.ctx);
  vm.runInContext(fragment("async function p0Fetch(","async function p0Run("),h.ctx);
  vm.runInContext("let p0ConnectionPromise = null;\n"+
    fragment("function p0ConnectionReady()","// Conversational shell:"),h.ctx);
  vm.runInContext(proposedSource.slice(proposedSource.indexOf("async function p0ResumeSaved()")),h.ctx);
  h.network=network;h.deadlines=deadlines;
  h.initial=()=>vm.runInContext("p0InitialConnection",h.ctx);
  h.resume=()=>h.node("r4-resume").listeners.click[0]();
  h.stall=options=>new Promise((resolve,reject)=>options.signal.addEventListener("abort",()=>reject(options.signal.reason),{once:true}));
  return h;
}
test("metadata deadline is 60 seconds and its timeout leaves generation unavailable without any command",async()=>{
  const h=connectionHarness((route,options)=>new Promise((resolve,reject)=>{
    options.signal.addEventListener("abort",()=>reject(options.signal.reason),{once:true});}));
  assert.equal(h.ctx.p0.busy,true);assert.equal(h.deadlines.size,1);
  const deadline=[...h.deadlines.values()][0];assert.equal(deadline.ms,60000);deadline.fn();await h.initial();
  assert.equal(h.ctx.p0.nonce,null);assert.equal(h.ctx.p0.connected,false);assert.equal(h.ctx.p0.uncertain,false);
  assert.equal(h.pe("generate").disabled,true);assert.match(h.pe("generate").textContent,/Génération indisponible/);
  assert.match(h.pe("status").textContent,/consultation locale a dépassé son délai/);
  assert.doesNotMatch(h.pe("status").textContent,/signal is aborted/);
  assert.equal(h.network.length,1);assert.equal(h.network[0].options.method,"GET");
});
test("resume clicked during initial connection waits once and the following revision sends the admitted nonce",async()=>{
  let complete;const h=connectionHarness(()=>new Promise(done=>{complete=()=>done(envelope(syntheticMetadata()));}));
  const resume=h.resume();await h.resume(); // Forced duplicate click cannot enqueue a second resume.
  assert.equal(h.ctx.r4ResumePending,true);assert.equal(h.ctx.p0.view,undefined);
  assert.match(h.node("r4-status").textContent,/attente de la connexion/);assert.equal(h.network.length,1);
  complete();await resume;
  assert.equal(h.ctx.p0.nonce,"N".repeat(43));assert.equal(h.ctx.p0.connected,true);
  assert.equal(h.ctx.p0.view.version_ref,syntheticView().version_ref);assert.equal(h.ctx.p0.busy,false);
  assert.equal(h.ctx.r4ResumePending,false);assert.equal(h.network.length,2);
  assert.equal(h.pe("generate").disabled,true);assert.match(h.pe("generate").textContent,/dans cette composition/);
  h.node("p0-edit-title").value="SYNTHETIC CHILD";await h.pe("revise").listeners.click[0]();
  const posts=h.network.filter(call=>call.options.method==="POST");assert.equal(posts.length,1);
  assert.equal(posts[0].route,"/api/v2/p0/revise");assert.equal(posts[0].options.headers["X-R2-Nonce"],"N".repeat(43));
  assert.equal(h.ctx.p0.view.title,"SYNTHETIC CHILD");assert.equal(h.ctx.p0.uncertain,false);
});
test("a changed saved selection during bootstrap wait cannot hydrate the old clicked version",async()=>{
  let complete;const h=connectionHarness(()=>new Promise(done=>{complete=()=>done(envelope(syntheticMetadata()));}));
  const pending=h.resume();h.ctx.r4Record={record:{origin:"LOCAL_APPLICATION",view:{...syntheticView(),version_ref:"ver:"+"9".repeat(32)}}};
  complete();await pending;
  assert.equal(h.ctx.p0.view,undefined);assert.equal(h.network.length,1);
  assert.match(h.node("r4-status").textContent,/sélection sauvegardée a changé/);assert.equal(h.ctx.r4ResumePending,false);
});
test("a failed metadata precondition blocks a forced revision before POST and preserves its uncommitted edit",async()=>{
  const h=connectionHarness(async()=>{throw new Error("SYNTHETIC_READ_FAILURE");});await h.initial();
  h.ctx.p0Render(syntheticView());h.node("p0-edit-title").value="EDIT NOT SENT";h.ctx.p0.dirty=true;
  await h.pe("revise").listeners.click[0]();
  assert.equal(h.network.filter(call=>call.options.method==="POST").length,0);assert.equal(h.network.length,2);
  assert.equal(h.ctx.p0.uncertain,false);assert.equal(h.ctx.p0.view.version_ref,syntheticView().version_ref);
  assert.equal(h.node("p0-edit-title").value,"EDIT NOT SENT");assert.equal(h.ctx.p0.dirty,true);
  assert.match(h.pe("status").textContent,/Aucun envoi de commande/);
  await h.resume();assert.match(h.node("r4-status").textContent,/Aucun envoi de commande/);
  assert.equal(h.network.filter(call=>call.options.method==="POST").length,0);
});
test("malformed nonce or authority cannot install metadata or dispatch a command",async()=>{
  for(const mutation of [{transport_nonce:"short"},{authority:"OWNER"},{live_binding:"OTHER_PORT"},{references:[{}]}]){
    const h=connectionHarness(async()=>envelope({...syntheticMetadata(),...mutation}));await h.initial();
    h.ctx.p0Render(syntheticView());await h.pe("revise").listeners.click[0]();
    assert.equal(h.ctx.p0.nonce,null);assert.equal(h.ctx.p0.connected,false);assert.equal(h.ctx.p0.liveBinding,"NONE");
    assert.equal(h.network.filter(call=>call.options.method==="POST").length,0);assert.equal(h.ctx.p0.uncertain,false);
    assert.match(h.pe("status").textContent,/Aucun envoi de commande/);
  }
});
test("a real POST timeout remains uncertain with one dispatch and no retry",async()=>{
  const h=connectionHarness();await h.initial();h.ctx.p0Render(syntheticView());
  h.ctx.fetch=async(route,options)=>{h.network.push({route,options});return h.stall(options);};
  const pending=h.pe("revise").listeners.click[0]();await flush();
  assert.equal(h.deadlines.size,1);assert.equal([...h.deadlines.values()][0].ms,10000);
  [...h.deadlines.values()][0].fn();await pending;
  assert.equal(h.network.filter(call=>call.options.method==="POST").length,1);assert.equal(h.ctx.p0.uncertain,true);
  assert.match(h.pe("status").textContent,/Aucun renvoi automatique/);
  await h.pe("revise").listeners.click[0]();assert.equal(h.network.filter(call=>call.options.method==="POST").length,1);
});
test("resume during another atelier action reports the pending action without silently claiming success",async()=>{
  const h=connectionHarness();await h.initial();h.ctx.p0.busy=true;await h.resume();
  assert.equal(h.network.length,1);assert.equal(h.ctx.p0.view,undefined);assert.equal(h.ctx.r4ResumePending,false);
  assert.match(h.node("r4-status").textContent,/action est déjà en cours/);
});
