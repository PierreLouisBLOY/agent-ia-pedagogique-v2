"use strict";
// Regression checks of shipped rendering functions; explicit synthetic DOM/data only.
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const assert=require("node:assert/strict"),{test}=require("node:test");
const source=fs.readFileSync(path.join(__dirname,"../../frontend/app.js"),"utf8");
const between=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)+1));
function harness(){
  const node=tag=>({tag,children:[],append(...items){this.children.push(...items);},
    set textContent(value){this.children=[String(value)];}});
  const ctx={document:{createElement:node,createTextNode:text=>String(text),addEventListener(){}},
    uxMediaAssets:(region,assets)=>assets.forEach(asset=>region.append({tag:"figure",children:[asset.visual_id]}))};
  vm.createContext(ctx);
  vm.runInContext(between("function classroomPreview(",'document.getElementById("r4-preview").addEventListener'),ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname,"../../frontend/real-course.js"),"utf8"),ctx);
  vm.runInContext(between("function uxTeacherBlocks(","function uxSavedCard("),ctx);
  return {ctx,node};
}
function chapter(){return {context:{title:"Situation",text:"CONTEXTE_ELEVE"},
  documents:[{id:"D1",title:"Données",text:"DOCUMENT_ELEVE",table:{columns:["Poste","Montant"],rows:[["Stock","300"]]}}],
  questions:[1,2,3,4,5].map(number=>({id:"Q"+number,number,prompt:"CONSIGNE_"+number,
    response:number===2?{lines:0,table:{columns:["Calcul","Valeur"],rows:[["FRNG",""]]}}:{lines:2,table:null}})),
  concepts:[{id:"N1",notion:"Notion",definition:"DEFINITION_ELEVE",explanation:"Méthode",example:"Exemple"}],
  parts:[{title:"Partie",document_ids:["D1"],observation:["Q1"],analysis:["Q2"],concept_ids:["N1"],reinvestment:["Q3"]}],
  knowledge_check:["Q4"],synthesis:"SYNTHESE_ELEVE",transfer:{title:"Transfert",document_ids:[],question_ids:["Q5"]},
  teacher_answers:[1,2,3,4,5].map(number=>({id:"Q"+number,expected_answer:"REPONSE_PROF_"+number,
    rationale:"RAISON_PROF_"+number,vigilance:"VIGILANCE_PROF_"+number,remediation:"AIDE_PROF_"+number}))};}
const flatten=item=>typeof item==="string"?item:item.children.map(flatten).join("");
test("rich COURSE uses observation, analysis, reinvestment and transfer roles; tables and response spaces remain native",()=>{
  const {ctx,node}=harness(),input=chapter(),before=JSON.stringify(input),blocks=ctx.uxCourseBlocks(input),out=node("article");
  ctx.classroomPreview(out,blocks);const text=flatten(out);
  for(const word of ["Observer","Analyser","Réinvestir","Tester ses connaissances","Transfert"])assert(text.includes(word));
  assert.deepEqual(Array.from(blocks.filter(block=>/^Q/.test(block.anchor_ref||"")).map(block=>block.anchor_ref)),["Q1","Q2","Q3","Q4","Q5"]);
  assert.equal(out.children.filter(item=>item.tag==="table").length,2);
  assert(text.includes("PosteMontantStock300"));assert(text.includes("CalculValeurFRNG"));assert(text.includes("…………"));
  assert.doesNotMatch(text,/REPONSE_PROF|RAISON_PROF|VIGILANCE_PROF|AIDE_PROF/);
  assert.equal(JSON.stringify(input),before,"No student/teacher source mutation");
});
test("rich teacher companions are rendered separately and anchored near context, document and question",()=>{
  const {ctx,node}=harness(),input=chapter(),before=JSON.stringify(input),student=node("article"),teacher=node("article");
  const assets=[{visual_id:"V_CONTEXT",section_ref:"CONTEXT",preferred_position:"AFTER_CONTEXT"},
    {visual_id:"V_DOC",section_ref:"D1",preferred_position:"AFTER_DOCUMENT"},
    {visual_id:"V_QUESTION",section_ref:"Q2",preferred_position:"AFTER_DOCUMENT"}];
  ctx.classroomPreview(student,ctx.uxCourseBlocks(input),assets);
  ctx.classroomPreview(teacher,ctx.uxTeacherBlocks({course_chapter:input},{course_chapter:input},"correction"),assets);
  const text=flatten(teacher);for(let i=1;i<=5;i++)for(const stem of ["REPONSE_PROF_","RAISON_PROF_","VIGILANCE_PROF_","AIDE_PROF_"])assert(text.includes(stem+i));
  assert.doesNotMatch(flatten(student),/REPONSE_PROF|RAISON_PROF|VIGILANCE_PROF|AIDE_PROF/);
  assert.equal(teacher.children.filter(item=>item.tag==="figure").length,3);
  const at=value=>teacher.children.findIndex(item=>flatten(item).includes(value));
  assert(at("CONTEXTE_ELEVE")<at("V_CONTEXT")&&at("V_CONTEXT")<at("DOCUMENT_ELEVE"));
  assert(at("Stock300")<at("V_DOC")&&at("V_DOC")<at("CONSIGNE_1"));
  assert(at("REPONSE_PROF_2")<at("V_QUESTION")&&at("V_QUESTION")<at("DEFINITION_ELEVE"));
  assert.equal(JSON.stringify(input),before);
  assert.throws(()=>ctx.uxTeacherBlocks({},{course_chapter:input},"marking"),/P0_COURSE_MARKING_NOT_AVAILABLE/);
});
test("removing a duplicated heading preserves its media at the rendered section before the following question",()=>{
  const {ctx,node}=harness(),out=node("article");
  ctx.classroomPreview(out,[{style:"Heading1",text:"Dossier",anchor_ref:"S1"},
    {style:"Normal",text:"## Dossier — Données\nCONTENU_DOCUMENT"},
    {style:"Heading2",text:"Question 1",anchor_ref:"Q1"},{style:"Normal",text:"CONSIGNE"}],
    [{visual_id:"VISUEL_DOCUMENT",section_ref:"S1",preferred_position:"AFTER_DOCUMENT"}]);
  assert.equal(out.children.filter(item=>item.tag==="h4"&&flatten(item).startsWith("Dossier")).length,1);
  assert.equal(out.children[2].tag,"figure");assert.equal(flatten(out.children[2]),"VISUEL_DOCUMENT");
  assert.equal(flatten(out.children[3]),"Question 1");
});
test("generic correction and marking preserve question anchors without mutating the learner preview",()=>{
  const {ctx,node}=harness(),view={sections:[{section_id:"S1",heading:"Situation",text:"ELEVE"}],questions:[{question_id:"Q1",prompt:"Calculer"}]},
    teacher={corrections:[{question_id:"Q1",expected_answer:"SECRET_PROF",rationale:"Justification"}],marking:[{question_id:"Q1",points:"4",criteria:["Méthode"]}]};
  const correction=node("article"),marking=node("article"),before=JSON.stringify(view);
  ctx.classroomPreview(correction,ctx.uxTeacherBlocks(view,teacher,"correction"),[{visual_id:"V_Q",section_ref:"Q1",preferred_position:"AFTER_DOCUMENT"}]);
  ctx.classroomPreview(marking,ctx.uxTeacherBlocks(view,teacher,"marking"));
  assert(flatten(correction).includes("SECRET_PROF"));assert.equal(correction.children.at(-1).tag,"figure");
  assert(flatten(marking).includes("4 pointsMéthode"));assert.doesNotMatch(flatten(marking),/SECRET_PROF/);
  assert.equal(JSON.stringify(view),before);
  assert.throws(()=>ctx.uxTeacherBlocks(view,{corrections:[]},"correction"),/P0_TEACHER_VIEW_BINDING/);
});

for(const position of ["AFTER_DOCUMENTS","AFTER_OBSERVATION","AFTER_ANALYSIS"]){
  test("progressive COURSE preserves "+position+" and both transfer activities",()=>{
    const {ctx,node}=harness(),input=chapter();
    input.parts[0].formalization=position;
    input.transfer=[input.transfer,{title:"Seconde activité",document_ids:[],question_ids:["Q6"]}];
    input.questions.push({id:"Q6",number:6,prompt:"CONSIGNE_6",response:{lines:2,table:null}});
    input.teacher_answers.push({id:"Q6",expected_answer:"REPONSE_PROF_6",rationale:"RAISON_PROF_6",vigilance:"VIGILANCE_PROF_6",remediation:"AIDE_PROF_6"});
    const before=JSON.stringify(input),blocks=ctx.uxCourseBlocks(input);
    const at=ref=>blocks.findIndex(block=>block.anchor_ref===ref);
    assert(at("D1")<at("N1"));
    assert(position==="AFTER_DOCUMENTS"?at("N1")<at("Q1"):at("Q1")<at("N1"));
    assert(position==="AFTER_ANALYSIS"?at("Q2")<at("N1"):at("N1")<at("Q2"));
    assert(at("N1")<at("Q3"));
    assert.deepEqual(Array.from(blocks.filter(block=>/^Q/.test(block.anchor_ref||"")).map(block=>block.anchor_ref)),["Q1","Q2","Q3","Q4","Q5","Q6"]);
    assert(blocks.findIndex(block=>block.text==="SYNTHESE_ELEVE")<at("Q4"));
    const student=node("article"),teacher=node("article");
    ctx.classroomPreview(student,blocks);
    ctx.classroomPreview(teacher,ctx.uxTeacherBlocks({course_chapter:input},{course_chapter:input},"correction"));
    assert(flatten(student).includes("Seconde activité"));
    assert.doesNotMatch(flatten(student),/REPONSE_PROF|RAISON_PROF|VIGILANCE_PROF|AIDE_PROF/);
    assert(flatten(teacher).includes("REPONSE_PROF_6"));
    assert.equal(JSON.stringify(input),before);
  });
}
