function uxCourseBlocks(chapter) {
  const blocks = [{style:"Heading1",text:chapter.context.title,anchor_ref:"CONTEXT"},
    {style:"Normal",text:chapter.context.text}];
  const a=chapter.assembly;
  if(a) blocks.push({style:"Normal",text:a.thread.notice});
  const documents = new Map(chapter.documents.map(item=>[item.id,item]));
  const questions = new Map(chapter.questions.map(item=>[item.id,item]));
  const concepts = new Map(chapter.concepts.map(item=>[item.id,item]));
  const question = ref => {const item=questions.get(ref);if (!item) throw new Error("P0_COURSE_VIEW_BINDING");
    blocks.push({style:"Heading2",text:"Question "+item.number,anchor_ref:ref},{style:"Normal",text:item.prompt});
    if (item.response.table) blocks.push({style:"Normal",text:"",table:item.response.table});
    else blocks.push({style:"Normal",text:Array(item.response.lines).fill("………………………………………………………………").join("\n")});
  };
  const document = ref => {const item=documents.get(ref);if (!item) throw new Error("P0_COURSE_VIEW_BINDING");
    blocks.push({style:"Heading2",text:item.title,anchor_ref:ref},{style:"Normal",text:item.text});
    if (item.table) blocks.push({style:"Normal",text:"",table:item.table});
  };
  const formalize=part=>part.concept_ids.forEach(ref=>{const item=concepts.get(ref);if(!item) throw new Error("P0_COURSE_VIEW_BINDING");
    blocks.push({style:"Heading2",text:item.notion,anchor_ref:ref},{style:"Normal",text:item.definition},
      {style:"Normal",text:item.explanation},{style:"Normal",text:item.example});
    if(a) blocks.push({style:"Normal",text:a.concept_vigilance.find(v=>v.id===ref).text});});
  chapter.parts.forEach(part=>{
    blocks.push({style:"Heading1",text:part.title});
    const meta=a?.parts.find(m=>m.id===part.id), early=meta?.formalization.position==="BEFORE_ACTIVITY";
    if(meta) blocks.push({style:"Normal",text:meta.transition});
    if(early) formalize(part);
    part.document_ids.forEach(document);
    const position=part.formalization || "AFTER_ANALYSIS";
    if(!early && position==="AFTER_DOCUMENTS") formalize(part);
    for(const role of ["observation","analysis"]){
      blocks.push({style:"Heading2",text:role==="observation"?"Observer":"Analyser"});part[role].forEach(question);
      if(!early && role==="observation" && position==="AFTER_OBSERVATION") formalize(part);}
    if(!early && position==="AFTER_ANALYSIS") formalize(part);
    blocks.push({style:"Heading2",text:"Réinvestir"});part.reinvestment.forEach(question);
  });
  const activities=Array.isArray(chapter.transfer)?chapter.transfer:[chapter.transfer];
  if(a || activities.length===2) blocks.push({style:"Heading1",text:"À retenir"},{style:"Normal",text:chapter.synthesis});
  blocks.push({style:"Heading1",text:"Tester ses connaissances"});chapter.knowledge_check.forEach(question);
  if(!a && activities.length===1) blocks.push({style:"Heading1",text:"À retenir"},{style:"Normal",text:chapter.synthesis});
  activities.forEach(activity=>{
    blocks.push({style:"Heading1",text:activity.title});
    activity.document_ids.forEach(document);activity.question_ids.forEach(question);
  });
  blocks.push(...p0RealSourceBlocks(chapter));
  return blocks;
}

function p0RealOrganizationOptions() {
  const panel=document.getElementById("p0-real-organization-panel");
  if(!panel) return;
  const rich=p0Element("family").value==="COURSE" && p0Element("course-format").value==="CHAPTER";
  panel.hidden=!rich;
  if (p0DocumentaryEnabled()) panel.hidden=true;
  const enabled=rich && !p0DocumentaryEnabled() && p0Element("real-organization").checked;
  const select=p0Element("organization"), prior=select.value;
  select.required=enabled; select.disabled=!enabled;
  select.replaceChildren(new Option("Choisir une organisation documentée",""));
  for(const item of p0.courseOrganizations || []) select.append(new Option(
    item.organization_label+" · "+item.source_count+" document(s)",item.organization_id));
  select.value=prior;
  p0Element("organization-note").textContent=enabled && !(p0.courseOrganizations||[]).length ?
    "Aucun dossier sourcé chargé. Le mode organisation réelle reste bloqué avant tout envoi." :
    "Les faits sourcés et les situations pédagogiques construites restent distingués.";
}
function p0RealOrganizationSelection(context) {
  if (p0DocumentaryEnabled()) return undefined;
  if(context.course_format!=="CHAPTER" || !p0Element("real-organization").checked) return undefined;
  const selected=(p0.courseOrganizations||[]).find(x=>x.organization_id===p0Element("organization").value);
  if(!selected) throw Object.assign(new Error("P0_REAL_ORGANIZATION_REQUIRED"),{confirmedRefusal:true});
  return {organization_id:selected.organization_id,dossier_sha256:selected.dossier_sha256};
}
function p0RealSourceBlocks(chapter) {
  const thread=chapter.organization_thread;
  if(!thread) return [];
  return [{style:"Heading1",text:"Organisation réelle et sources"},{style:"Normal",text:thread.notice},
    ...thread.sources.flatMap(s=>[{style:"Heading2",text:s.title},
      {style:"Normal",text:s.publisher+" · "+s.retrieved_on+"\n"+s.source_url+"\n"+s.rights}])];
}
document.addEventListener("DOMContentLoaded",()=>{
  p0Element("real-organization").addEventListener("change",p0RealOrganizationOptions);
  p0Element("organization-suggest").addEventListener("click",()=>{
    const notions=new Set([...p0Element("program-notions").selectedOptions].map(o=>o.value));
    const ranked=(p0.courseOrganizations||[]).map(item=>({item,
      score:item.notion_refs.filter(n=>notions.has(n)).length}))
      .filter(x=>x.score>0).sort((a,b)=>b.score-a.score || a.item.organization_label.localeCompare(b.item.organization_label));
    if(!ranked.length) {p0Element("organization-note").textContent="Aucun dossier chargé ne correspond aux notions choisies.";return;}
    p0Element("organization").value=ranked[0].item.organization_id;
    p0Element("organization").dispatchEvent(new Event("change",{bubbles:true}));
    p0Element("organization-note").textContent="Proposition fondée sur les documents disponibles. Consultez les sources avant de préparer.";
  });
  p0Element("organization-inspect").addEventListener("click",()=>p0Run(async()=>{
    const selected=(p0.courseOrganizations||[]).find(x=>x.organization_id===p0Element("organization").value);
    if(!selected) throw Object.assign(new Error("P0_REAL_ORGANIZATION_REQUIRED"),{confirmedRefusal:true});
    const result=await p0Fetch("/api/v2/p0/organizations/"+selected.organization_id);
    if(result.dossier_sha256!==selected.dossier_sha256 || !result.course_dossier) throw new Error("P0_REAL_ORGANIZATION_CHANGED");
    const out=p0Element("organization-sources");out.replaceChildren();
    appendSearchText(out,"h4",selected.organization_label);
    appendSearchText(out,"p",result.course_dossier.identity.fact);
    for(const s of result.course_dossier.documents) {
      appendSearchText(out,"h4",s.title);appendSearchText(out,"p",s.excerpt);
      appendSearchText(out,"p",s.publisher+" · "+s.retrieved_on+" · "+s.source_url+" · "+s.rights);
    }
    appendSearchText(out,"p","Dossier exact : "+result.dossier_sha256+". Aucune admission canonique ni autorisation d’envoi créée.");
  }));
});
