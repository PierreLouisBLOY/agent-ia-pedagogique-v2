"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync("frontend/app.js", "utf8");
const code = source.slice(source.indexOf("function proposePreparation("), source.indexOf("function uxContext("));
const sandbox = {}; vm.createContext(sandbox); vm.runInContext(code, sandbox);
for (const [phrase, family, level] of [
  ["Un cours première STMG sur les organisations", "COURSE", "FIRST_STMG"],
  ["Un exercice BTS CG deuxième année sur le coût", "EXERCISE", "BTS_CG_YEAR_2"],
  ["Questions ouvertes terminale STMG sur la performance", "OPEN_QUESTIONS", "FINAL_STMG"],
  ["QCM BTS CG 1 sur le lettrage", "QCM", "BTS_CG_YEAR_1"],
  ["Quiz terminale STMG sur le management", "QUIZ", "FINAL_STMG"],
  ["Une évaluation BTS CG 2 sur le BFR, durée 60 minutes, noté sur 20", "ASSESSMENT", "BTS_CG_YEAR_2"]
]) {
  const result = sandbox.proposePreparation(phrase);
  assert.equal(result.family, family); assert.equal(result.level, level); assert.equal(result.ambiguities.length, 0);
}
const ambiguous = sandbox.proposePreparation("Cours ou quiz BTS CG sur la TVA");
assert.equal(ambiguous.family, ""); assert.equal(ambiguous.level, ""); assert.equal(ambiguous.ambiguities.length, 2);
assert.equal(sandbox.proposePreparation("Évaluation BTS CG 2 sur le BFR de 1 heure notée sur 20").duration, 60);
assert.equal(sandbox.proposePreparation("x".repeat(501)).objective, "");
assert(!source.includes("localStorage")); assert(!source.includes("innerHTML"));
const html = fs.readFileSync("frontend/index.html", "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(ids.length, new Set(ids).size);
for (const key of ["preparation-composer", "production-card", "sources-drawer", "session-conversations"]) assert(ids.includes(key));
console.log("CONVERSATION_SHELL: 6 families, 4 levels, ambiguity, duration, length, safe DOM, closed storage, unique IDs PASS");

// Execute the actual teacher projection: no answer enters the student preview
// and readonly consultation does not enable or mutate the editing companion.
async function checkTeacherCards() {
  const regions = {"production-card-preview": {children:["STUDENT SUBJECT"]},
    "production-card-teacher-preview": {children:[],replaceChildren(){this.children=[];}}};
  const status={}; let requests=0;
  const ctx={p0:{view:{production_ref:"prod:fixture",version_ref:"ver:fixture"},teacher:null},
    document:{getElementById:id=>regions[id]},p0Element:()=>status,
    p0Run:async action=>action(),
    p0Fetch:async path=>{requests++;assert.equal(path,"/api/v2/p0/versions/prod:fixture/ver:fixture/teacher");
      return {corrections:[{question_id:"Q1",expected_answer:"TEACHER ANSWER",rationale:"TEACHER METHOD"}],
        marking:[{question_id:"Q1",points:"20.00",criteria:["TEACHER CRITERION"]}]};},
    appendSearchText:(region,tag,text)=>region.children.push({tag,text})};
  vm.createContext(ctx);
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
  ctx.p0.nonce="fixture";ctx.p0.view={questions:[],pedagogical_context:{resource_type:"COURSE"}};
  ctx.p0Controls(); assert(controls["card-correction"].disabled&&controls["card-marking"].disabled);
  ctx.p0.view.course_chapter={contract_id:"COURSE-CHAPTER-1.0"};
  ctx.p0Controls(); assert(!controls["card-correction"].disabled&&controls["card-marking"].disabled);
  ctx.document.getElementById=id=>regions[id] || (controls[id]||= {});
  ctx.p0Fetch=async()=>({corrections:[],marking:[],course_chapter:{teacher_answers:[{id:"Q1",expected_answer:"COURSE TEACHER ANSWER",rationale:"COURSE METHOD",vigilance:"COURSE CHECK",remediation:"COURSE SUPPORT"}]}});
  await ctx.uxTeacherCard("correction");
  assert(regions["production-card-teacher-preview"].children.some(n=>n.text==="COURSE TEACHER ANSWER"));
  assert.equal(regions["production-card-preview"].children.join(),"STUDENT SUBJECT");
  assert.equal(ctx.p0.teacher,null);
  ctx.p0.view={questions:[{}],pedagogical_context:{resource_type:"ASSESSMENT"}};
  ctx.p0Controls(); assert(!controls["card-correction"].disabled&&!controls["card-marking"].disabled);
  ctx.p0.uncertain=true;ctx.p0Controls(); assert(controls["card-export"].disabled);
  console.log("CARD_ACTIONS: separate teacher projections, immutable student/edit memory, unavailable family and uncertain-write controls PASS");
}
checkTeacherCards().catch(error=>{console.error(error);process.exitCode=1;});
