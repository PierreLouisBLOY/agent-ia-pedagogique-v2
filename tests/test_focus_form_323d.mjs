// Unit checks of the actual UI functions; browser qualification is separate.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source=fs.readFileSync(new URL("../frontend/app.js",import.meta.url),"utf8");
const helpers=fs.readFileSync(new URL("../frontend/normal-on.js",import.meta.url),"utf8");
const code=source.slice(source.indexOf("function p0Context()"),source.indexOf("function p0CourseFormatOptions()"))+helpers.slice(helpers.indexOf("function p0ExerciseQuestionParts("));
const nodes=new Map();
const node=(id)=>{if(!nodes.has(id))nodes.set(id,{value:"",selectedOptions:[],children:[],replaceChildren(){this.children=[];},append(o){this.children.push(o);}});return nodes.get(id);};
const local="Comment un individu devient-il acteur dans une organisation ?";
const question={question_ref:"question:SYNTHETIC",theme_ref:"theme:1",label:"1.1 Types d'organisation ? "+local,source_question_sha256:"a".repeat(64)};
const frame={frame:"SGN_PREMIERE",education_level:"PREMIERE",teaching_subject:"SCIENCES_GESTION_NUMERIQUE",program_ref:"program:SYNTHETIC",program_version:"version:SYNTHETIC",program_component:"SPECIALITE",specific_track:null,label:"Sciences de gestion et numérique",questions:[question]};
let invalidations=0;
const context={p0Element:node,p0Lines:(id)=>node(id).value.split("\n").filter(Boolean),p0InstitutionalFrame:()=>frame,
 document:{createElement:()=>({value:"",textContent:""})},p0:{prepared:{},consent:{}},
 p0Invalidate(){invalidations++;context.p0.prepared=null;context.p0.consent=null;}};
vm.createContext(context);vm.runInContext(code,context);
for(const [id,value] of Object.entries({family:"EXERCISE",level:"FIRST_STMG",discipline:frame.label,topics:"Attitude\nComportement",objectives:"Caractériser les comportements",difficulty:"STANDARD","program-question":question.question_ref,depth:"APPLICATION","exercise-format":"SIMPLE"}))node(id).value=value;
node("capacities").selectedOptions=[{value:"capacity:SYNTHETIC"}];node("program-notions").selectedOptions=[{value:"notion:SYNTHETIC"}];
context.p0ExerciseFocusOptions();
let value=context.p0Context();
assert.equal(value.contract_id,"P0-CONTEXT-2.0");assert.ok(!("exercise_focus_selection" in value));assert.ok(!("exercise_focus_justification" in value));
node("exercise-format").value="STRUCTURED";context.p0ExerciseFocusOptions();
assert.equal(node("exercise-focus").value,"");assert.equal(node("exercise-focus").children.length,3);
assert.throws(()=>context.p0Context(),/EXERCISE_EXPLICIT_FOCUS_REQUIRED/);
node("exercise-focus").value=local;assert.throws(()=>context.p0Context(),/EXERCISE_EXPLICIT_FOCUS_REQUIRED/);
node("exercise-justification").value="Focalisation pédagogique explicite, sans modification du programme.";
value=context.p0Context();assert.equal(value.contract_id,"P0-CONTEXT-EXERCISE-1.1");assert.equal(value.exercise_focus_selection.source_question_sha256,question.source_question_sha256);assert.equal(value.exercise_focus_selection.local_question_label,local);
question.source_question_sha256="b".repeat(64);context.p0ExerciseFocusOptions();assert.equal(node("exercise-focus").value,"");assert.equal(node("exercise-justification").value,"");assert.ok(invalidations>=3);
assert.equal(context.p0ExerciseQuestionParts("1.1 A ? B ?")[0],"1.1 A ?");assert.equal(context.p0ExerciseQuestionParts("A ? suffixe").length,0);
assert.equal(context.p0ExerciseQuestionParts("A ? ?").length,0);assert.equal(context.p0ExerciseQuestionParts("?").length,0);
node("exercise-format").value="UNSUPPORTED";assert.throws(()=>context.p0Context(),/EXERCISE_FORMAT_REQUIRED/);
node("exercise-format").value="SIMPLE";context.p0ExerciseFocusOptions();value=context.p0Context();assert.ok(!("exercise_focus_selection" in value));
console.log(JSON.stringify({status:"PASS",scope:"Actual UI functions with synthetic DOM only",source_hash_used_without_recomputing_abbreviation:true,no_automatic_component_selection:true,invalidated_on_source_change:true,browser_proof_separate:true}));
