"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync("frontend/app.js", "utf8");

test("COURSE editor preserves readonly identities and separates teacher edits", () => {
  const controls = {"p0-edit-title": {value: "Titre du cours"}};
  const ctx = {document: {getElementById: id => controls[id]},
    p0Field: (region,id,label,value) => {controls[id] = {value};region.push(id);},
    appendSearchText: () => {}};
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf("function p0CourseFields("),source.indexOf("function p0MediaOptions(")),ctx);
  const chapter = {context:{title:"Situation",text:"Données fictives"},
    documents:[{id:"D1",title:"Document",text:"Observation",function:"Observe",provenance:"UNEXPOSED"}],
    questions:[{id:"Q1",prompt:"Analyser",capability_ids:["C1"]}],
    concepts:[{id:"N1",definition:"Définition",explanation:"Méthode",example:"Exemple",notion:"Notion"}],
    parts:[{id:"P1",title:"Partie",document_ids:["D1"]}],synthesis:"Synthèse",
    program_header:{question_ref:"READ_ONLY"}};
  const original=JSON.stringify(chapter), student=[];
  ctx.p0CourseFields(student,chapter);
  assert(!student.some(id=>id.includes("teacher")));
  let edits=JSON.parse(JSON.stringify(ctx.p0CourseEdits(chapter)));
  assert.deepEqual(edits,{title:"Titre du cours",course_edits:{}});
  controls["p0-course-questions-prompt-0"].value="Consigne révisée";
  edits=JSON.parse(JSON.stringify(ctx.p0CourseEdits(chapter)));
  assert.deepEqual(edits.course_edits,{questions:[{id:"Q1",prompt:"Consigne révisée"}]});
  assert(!JSON.stringify(edits).includes("READ_ONLY"));
  const teacher={teacher_answers:[{id:"Q1",expected_answer:"TEACHER_ONLY",rationale:"Méthode",vigilance:"Vigilance",remediation:"Aide"}]};
  ctx.p0CourseFields([],teacher,true);
  controls["p0-course-teacher-expected_answer-0"].value="TEACHER_NEW";
  edits=JSON.parse(JSON.stringify(ctx.p0CourseEdits(chapter,teacher)));
  assert.deepEqual(edits.course_edits.teacher_answers,[{id:"Q1",expected_answer:"TEACHER_NEW"}]);
  assert.equal(JSON.stringify(chapter),original);
});

test("media selection is local, bound to the exact admitted context, and contains no authority input", () => {
  const controls={"media-reason":{value:"Aider à ordonner la méthode"},"media-mode":{value:"NO_MEDIA"},
    "media-capacity":{value:"capacity:TEST"},"media-objective":{value:"Ordonner les étapes"},
    "media-anchor":{value:"S1"},"media-nodes":{value:"Observer\nAnalyser\nCalculer\nContrôler"},
    "media-caption":{value:"Quatre étapes à appliquer"},"media-required":{checked:true}};
  const ctx={p0Element:id=>controls[id],p0Command:()=>"a".repeat(32)};
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf("function p0MediaSelection("),source.indexOf('p0Element("media-mode").addEventListener')),ctx);
  const view={production_ref:"prod:fixture",sections:[{section_id:"S1"}],pedagogical_context:{
    objectives:["Ordonner les étapes"],institutional:{capacity_refs:["capacity:TEST"],notion_refs:["notion:TEST"]},
    institutional_resolution:{status:"RESOLVED_ADMITTED"}}};
  assert.deepEqual(JSON.parse(JSON.stringify(ctx.p0MediaSelection(view))),{mode:"NO_MEDIA",reason:"Aider à ordonner la méthode"});
  controls["media-mode"].value="LOCAL_DIAGRAM";
  const selection=JSON.parse(JSON.stringify(ctx.p0MediaSelection(view)));
  assert.equal(selection.entries[0].brief.production_ref,view.production_ref);
  assert.deepEqual(selection.entries[0].dependency_refs,["section:S1"]);
  assert.equal(selection.entries[0].brief.source_policy,"LOCAL_DETERMINISTIC");
  assert.equal(selection.entries[0].brief.diagram.nodes.length,4);
  assert(!JSON.stringify(selection).includes("bytes_base64"));
  for(const alteration of [()=>{view.pedagogical_context.institutional_resolution.status="CONTENT_GAP";},
    ()=>{controls["media-capacity"].value="capacity:WRONG";},()=>{controls["media-anchor"].value="S_WRONG";}]) {
    const saved=structuredClone(view), values=structuredClone(controls);alteration();
    assert.throws(()=>ctx.p0MediaSelection(view),/P0_MEDIA_CONTEXT_REQUIRED/);
    Object.assign(view,saved);for(const key of Object.keys(controls))Object.assign(controls[key],values[key]);
  }
  controls["media-nodes"].value="Observer\nObserver\nCalculer\nContrôler";
  assert.throws(()=>ctx.p0MediaSelection(view),/P0_MEDIA_FOUR_DISTINCT_STEPS_REQUIRED/);
});

test("media preview only uses PNG data and rejects remote assets", () => {
  const region={children:[],append(node){this.children.push(node);}};
  const ctx={document:{createElement:()=>({children:[],append(node){this.children.push(node);}})},
    appendSearchText:(parent,tag,text)=>parent.children.push({tag,text})};
  vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf("function uxMediaAssets("),source.indexOf("async function uxTeacherCard(")),ctx);
  const asset={mime_type:"image/png",bytes_base64:"iVBORw0KGgoTEST_DISPLAY_DOUBLE",png_sha256:"a".repeat(64),
    alt_text:"Description",caption:"Légende",width:800,height:500};
  ctx.uxMediaAssets(region,[asset]);assert.equal(region.children[0].children[0].alt,"Description");
  assert(region.children[0].children[0].src.startsWith("data:image/png;base64,"));
  assert.throws(()=>ctx.uxMediaAssets(region,[{...asset,bytes_base64:"https://unapproved.example/image.png"}]),/P0_MEDIA_VIEW_REJECTED/);
  assert.equal(region.children.length,1);
});

test("preview inserts media at its exact section before the next section and rejects missing or duplicate anchors", () => {
  const ctx={document:{createElement:tag=>({tag,children:[],append(...nodes){this.children.push(...nodes);}}),
    createTextNode:text=>({text})},uxMediaAssets:(target,assets)=>assets.forEach(asset=>target.append({figure:asset.visual_id})),
    output:{children:[],append(...nodes){this.children.push(...nodes);}}};
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf("function classroomPreview("),source.indexOf('document.getElementById("r4-preview").addEventListener')),ctx);
  const blocks=[{style:"Heading1",text:"Situation",anchor_ref:"S01"},{style:"Normal",text:"Observation"},
    {style:"Heading2",text:"Question 1",anchor_ref:"Q01"},{style:"Normal",text:"Analysez"}];
  const asset={visual_id:"V01",section_ref:"S01",preferred_position:"AFTER_DOCUMENT"};
  ctx.classroomPreview(ctx.output,blocks,[asset]);
  assert.equal(ctx.output.children[2].figure,"V01");
  assert.equal(ctx.output.children.length,5);
  assert.throws(()=>ctx.classroomPreview(ctx.output,blocks,[{...asset,section_ref:"S99"}]),/ANCHOR_UNAVAILABLE/);
  assert.throws(()=>ctx.classroomPreview(ctx.output,[...blocks,blocks[0]],[asset]),/ANCHOR_UNAVAILABLE/);
  const fromWord={...asset,anchor_heading:"Situation"};
  const wordOutput={children:[],append(...nodes){this.children.push(...nodes);}};
  ctx.classroomPreview(wordOutput,blocks,[fromWord]);assert.equal(wordOutput.children[2].figure,"V01");
});

test("exports are limited to the actual family and separate rich COURSE teacher projection", () => {
  const ctx={};vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf("function r4AvailableKinds("),source.indexOf("function r4Controls(")),ctx);
  for (const [resource_type,rich,expected] of [["ASSESSMENT",false,["student","correction","marking"]],
    ["EXERCISE",false,["student","correction"]],["QUESTION_SET",false,["student","correction"]],
    ["COURSE",false,["student"]],["COURSE",true,["student","correction"]]]) {
    const record={bundle:{context:{resource_type},...(rich?{course_chapter:{}}:{})}};
    assert.deepEqual(Array.from(ctx.r4AvailableKinds(record)),expected);
  }
});
