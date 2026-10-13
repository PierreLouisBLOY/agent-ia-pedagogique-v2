"use strict";
// Actual shipped context builders, with declared synthetic DOM/catalogue fixtures.
const assert=require("node:assert/strict"), fs=require("node:fs"), vm=require("node:vm"), path=require("node:path");
const {test}=require("node:test");
const fixture=fs.readFileSync(path.join(__dirname,"stmg_context.test.cjs"),"utf8");
const sandbox={require,__dirname,console};vm.createContext(sandbox);
vm.runInContext(fixture.slice(0,fixture.indexOf("for(const frame of frames)")),sandbox);
vm.runInContext("globalThis.h={node,sandbox,frames};",sandbox);
const h=sandbox.h;
function select(level="FIRST_STMG"){
 h.node("level").value=level;h.sandbox.p0InstitutionalOptions();
 const frame=h.frames.find(f=>f.level===level);
 h.node("frame").value=frame.program_version;h.sandbox.p0InstitutionalQuestionOptions();
 h.node("program-question").value=frame.questions[0].question_ref;h.sandbox.p0InstitutionalCapacityOptions();
 h.node("capacities").selectedOptions=[{value:frame.capacities[0].capacity_ref}];
 h.node("program-notions").selectedOptions=[{value:"notion:shared"}];h.node("depth").value="APPLICATION";
}
test("rich COURSE is selected visibly, hashes its format, and requires a local number",()=>{
 select();h.node("course-format").value="CHAPTER";h.node("local-chapter").value="1";
 h.sandbox.p0CourseFormatOptions();const rich=h.sandbox.p0Context();
 assert.equal(rich.contract_id,"P0-CONTEXT-COURSE-3.0");assert.equal(rich.course_format,"CHAPTER");
 assert.equal(rich.local_progression.chapter,"1");assert.equal(h.node("local-chapter").required,true);
 for(const invalid of ["","01","0","100","Chapitre II"," 1"]) {
  h.node("local-chapter").value=invalid;assert.throws(()=>h.sandbox.p0Context(),/CHAPTER_NUMBER/);
 }
 h.node("course-format").value="EXPLAINED";h.node("local-chapter").value="Chapitre local II";h.sandbox.p0CourseFormatOptions();
 assert.equal(h.node("local-chapter").required,false);assert.equal(h.sandbox.p0Context().course_format,"EXPLAINED");
});
test("other families retain the old institution context and receive no course format",()=>{
 h.node("family").value="QUIZ";select();h.sandbox.p0CourseFormatOptions();
 const quiz=h.sandbox.p0Context();assert.equal(quiz.contract_id,"P0-CONTEXT-2.0");
 assert.equal(quiz.resource_type,"QUESTION_SET");assert.equal(quiz.question_mode,"QUIZ");
 assert(!Object.hasOwn(quiz,"course_format"));assert.equal(h.node("course-format-panel").hidden,true);
});
test("no missing format falls back to rich or explained",()=>{
 h.node("family").value="COURSE";select();h.node("course-format").value="";
 assert.throws(()=>h.sandbox.p0Context(),/COURSE_FORMAT_REQUIRED/);
});
