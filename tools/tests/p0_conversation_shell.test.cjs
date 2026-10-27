"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync("frontend/app.js", "utf8");
const code = source.slice(source.indexOf("async function proposePreparation("), source.indexOf("function uxContext("));
async function checkApplicationIntention() {
  for (const [phrase, family, level] of [
    ["Un cours première STMG sur les organisations", "COURSE", "FIRST_STMG"],
    ["Un exercice BTS CG deuxième année sur le coût", "EXERCISE", "BTS_CG_YEAR_2"],
    ["Questions ouvertes terminale STMG sur la performance", "OPEN_QUESTIONS", "FINAL_STMG"],
    ["QCM BTS CG 1 sur le lettrage", "QCM", "BTS_CG_YEAR_1"],
    ["Quiz terminale STMG sur le management", "QUIZ", "FINAL_STMG"],
    ["Une évaluation BTS CG 2 sur le BFR, durée 60 minutes, noté sur 20", "ASSESSMENT", "BTS_CG_YEAR_2"]
  ]) {
    let calls=0;
    const ctx={p0Command:()=>"a".repeat(32),p0Fetch:async(path,body)=>{
      calls++;assert.equal(path,"/api/v2/p0/intention");
      assert.deepEqual(Object.keys(body).sort(),["command_id","intention"]);
      assert.equal(body.intention,phrase);
      return {contract_id:"P0-INTENTION-PROPOSAL-1.0",command_id:body.command_id,
        implementation:"DETERMINISTIC_APPLICATION_PROPOSAL",authority:"NONE",
        confirmation_required:true,provider_attempts:0,proposal:{family,level}};
    }};
    vm.createContext(ctx);vm.runInContext(code,ctx);
    const result=await ctx.proposePreparation(phrase);
    assert.equal(result.proposal.family,family);assert.equal(result.proposal.level,level);assert.equal(calls,1);
  }
  for(const mutation of ["command_id","authority","contract_id","confirmation_required","provider_attempts","implementation"]){
    const response={contract_id:"P0-INTENTION-PROPOSAL-1.0",command_id:"a".repeat(32),
      implementation:"DETERMINISTIC_APPLICATION_PROPOSAL",authority:"NONE",
      confirmation_required:true,provider_attempts:0};
    response[mutation]=mutation==="provider_attempts"?1:mutation==="confirmation_required"?false:"WRONG";
    const ctx={p0Command:()=>"a".repeat(32),p0Fetch:async()=>response};
    vm.createContext(ctx);vm.runInContext(code,ctx);
    await assert.rejects(ctx.proposePreparation("Demande"),/P0_INTENTION_RESPONSE_REJECTED/);
  }
  console.log("APPLICATION_INTENTION: 6 family/level proposals carried through Application boundary; 6 substituted envelopes rejected PASS. Interpretation tested by Application suite.");
}
checkApplicationIntention().catch(error=>{console.error(error);process.exitCode=1;});
assert(!source.includes("localStorage")); assert(!source.includes("innerHTML"));
const html = fs.readFileSync("frontend/index.html", "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(ids.length, new Set(ids).size);
for (const key of ["preparation-composer", "production-card", "sources-drawer", "session-conversations"]) assert(ids.includes(key));
console.log("CONVERSATION_SHELL: safe DOM, closed storage, unique IDs PASS");

// Execute the actual teacher projection: no answer enters the student preview
// and readonly consultation does not enable or mutate the editing companion.
async function checkTeacherCards() {
  const regions = {"production-card-preview": {children:["STUDENT SUBJECT"]},
    "production-card-teacher-preview": {children:[],replaceChildren(){this.children=[];}}};
  const status={}; let requests=0;
  const ctx={p0:{view:{production_ref:"prod:fixture",version_ref:"ver:fixture",bundle_sha256:"a".repeat(64),
    sections:[{section_id:"S1",heading:"Situation synthétique",text:"STUDENT SUBJECT"}],
    questions:[{question_id:"Q1",prompt:"CONSIGNE SYNTHÉTIQUE",options:[]}]},teacher:null},
    document:{getElementById:id=>regions[id]},p0Element:()=>status,
    p0Run:async action=>action(),
    p0Fetch:async path=>{requests++;assert.equal(path,"/api/v2/p0/versions/prod:fixture/ver:fixture/teacher");
      return {production_ref:"prod:fixture",version_ref:"ver:fixture",bundle_sha256:"a".repeat(64),corrections:[{question_id:"Q1",expected_answer:"TEACHER ANSWER",rationale:"TEACHER METHOD"}],
        marking:[{question_id:"Q1",points:"20.00",criteria:["TEACHER CRITERION"]}]};},
    appendSearchText:(region,tag,text)=>region.children.push({tag,text}),uxMediaAssets:(region,assets)=>assert.equal(assets.length,0),
    // Explicit layout double: the rich/native renderer is checked separately.
    classroomPreview:(region,blocks,assets)=>{assert.equal(assets.length,0);
      blocks.forEach(block=>region.children.push({tag:block.style,text:block.text}));}};
  ctx.p0Identity=()=>({production_ref:ctx.p0.view.production_ref,version_ref:ctx.p0.view.version_ref,bundle_sha256:ctx.p0.view.bundle_sha256});
  ctx.p0DisplayedVersion=target=>Object.keys(target).every(k=>ctx.p0.view[k]===target[k]);
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf("function uxCourseBlocks("),source.indexOf("function uxMediaAssets(")),ctx);
  vm.runInContext(source.slice(source.indexOf("async function uxTeacherCard("),source.indexOf("function uxSavedCard(")),ctx);
  await ctx.uxTeacherCard("correction");
  assert.equal(regions["production-card-preview"].children.join(),"STUDENT SUBJECT");
  assert(regions["production-card-teacher-preview"].children.some(n=>n.text==="TEACHER ANSWER"));
  assert(!regions["production-card-teacher-preview"].children.some(n=>n.text==="TEACHER CRITERION"));
  await ctx.uxTeacherCard("marking");
  assert(regions["production-card-teacher-preview"].children.some(n=>n.text==="TEACHER CRITERION"));
  assert(!regions["production-card-teacher-preview"].children.some(n=>n.text==="TEACHER ANSWER"));
  assert.equal(ctx.p0.teacher,null); assert.equal(requests,2);
  const controls={};ctx.document.getElementById=id=>controls[id]||= {};
  ctx.p0Element=id=>controls[id]||= {};
  vm.runInContext(source.slice(source.indexOf("function p0Controls("),source.indexOf("async function p0Fetch(")),ctx);
  ctx.p0.nonce="fixture";ctx.p0.view={production_ref:"prod:fixture",version_ref:"ver:fixture",bundle_sha256:"a".repeat(64),questions:[],pedagogical_context:{resource_type:"COURSE"}};
  ctx.p0Controls(); assert(controls["card-correction"].disabled&&controls["card-marking"].disabled);
  ctx.p0.view.course_chapter={contract_id:"COURSE-CHAPTER-1.0"};
  ctx.p0Controls(); assert(!controls["card-correction"].disabled&&controls["card-marking"].disabled);
  ctx.document.getElementById=id=>regions[id] || (controls[id]||= {});
  ctx.p0Fetch=async()=>({production_ref:"prod:fixture",version_ref:"ver:fixture",bundle_sha256:"a".repeat(64),corrections:[],marking:[],
    course_chapter:{context:{title:"Situation synthétique",text:"CONTEXTE ÉLÈVE"},documents:[],concepts:[],
      questions:[{id:"Q1",number:1,prompt:"CONSIGNE SYNTHÉTIQUE",response:{lines:2,table:null}}],
      parts:[{title:"Partie",document_ids:[],observation:["Q1"],analysis:[],concept_ids:[],reinvestment:[]}],
      knowledge_check:[],synthesis:"SYNTHÈSE",transfer:{title:"Transfert",document_ids:[],question_ids:[]},
      teacher_answers:[{id:"Q1",expected_answer:"COURSE TEACHER ANSWER",rationale:"COURSE METHOD",vigilance:"COURSE CHECK",remediation:"COURSE SUPPORT"}]}});
  await ctx.uxTeacherCard("correction");
  assert(regions["production-card-teacher-preview"].children.some(n=>n.text==="COURSE TEACHER ANSWER"));
  assert.equal(regions["production-card-preview"].children.join(),"STUDENT SUBJECT");
  assert.equal(ctx.p0.teacher,null);
  const preserved=JSON.stringify(regions["production-card-teacher-preview"].children);
  ctx.p0Fetch=async()=>({production_ref:"prod:fixture",version_ref:"ver:WRONG",bundle_sha256:"a".repeat(64),corrections:[],marking:[]});
  await assert.rejects(ctx.uxTeacherCard("correction"),/P0_TEACHER_VERSION_CHANGED/);
  assert.equal(JSON.stringify(regions["production-card-teacher-preview"].children),preserved);
  ctx.p0Fetch=async()=>{const old=ctx.p0Identity();ctx.p0.view={...ctx.p0.view,version_ref:"ver:new"};
    return {...old,corrections:[{expected_answer:"LATE_ANSWER"}],marking:[]};};
  await assert.rejects(ctx.uxTeacherCard("correction"),/P0_TEACHER_VERSION_CHANGED/);
  assert.equal(JSON.stringify(regions["production-card-teacher-preview"].children),preserved);
  ctx.p0.view={questions:[{}],pedagogical_context:{resource_type:"ASSESSMENT"}};
  ctx.p0Controls(); assert(!controls["card-correction"].disabled&&!controls["card-marking"].disabled);
  ctx.p0.uncertain=true;ctx.p0Controls(); assert(controls["card-export"].disabled);
  console.log("CARD_ACTIONS: separate teacher projections, immutable student/edit memory, unavailable family and uncertain-write controls PASS");
}
checkTeacherCards().catch(error=>{console.error(error);process.exitCode=1;});
