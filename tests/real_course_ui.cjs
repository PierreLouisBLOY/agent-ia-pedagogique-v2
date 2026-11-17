// Exercises the shipped helper, with a small DOM and no network/provider.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {value:'',checked:true,hidden:true,children:[],listeners:{},
    replaceChildren(...items){this.children=items;},append(item){this.children.push(item);},
    addEventListener(type,callback){this.listeners[type]=callback;},
    dispatchEvent(event){this.lastEvent=event.type;}});
  return nodes.get(id);
}
const source={title:'<script>must remain text</script>',excerpt:'EXACT SYNTHETIC EXCERPT',
  publisher:'Synthetic publisher',retrieved_on:'2026-10-29',source_url:'https://example.org/source',rights:'Synthetic'};
const catalogue={organization_id:'siren:123456789',organization_label:'SYNTHETIC ORGANIZATION',
  source_count:1,dossier_sha256:'a'.repeat(64),notion_refs:['notion:test']};
let ready, fetches=0, documentaryEnabled=false;
const context={document:{getElementById:node,addEventListener(type,callback){assert.equal(type,'DOMContentLoaded');ready=callback;}},
  p0Element:id=>node('p0-'+id),p0:{courseOrganizations:[]},
  Option:function(text,value){return {text,value};},Event:function(type){this.type=type;},
  p0DocumentaryEnabled:()=>documentaryEnabled,
  p0Run:callback=>callback(),appendSearchText:(out,tag,text)=>out.children.push({tag,text}),
  p0Fetch:async url=>{fetches++;assert.equal(url,'/api/v2/p0/organizations/'+catalogue.organization_id);
    return {dossier_sha256:catalogue.dossier_sha256,course_dossier:{identity:{fact:'SYNTHETIC IDENTITY'},documents:[source]}};}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/real-course.js'),'utf8'),context);
ready();
node('p0-family').value='COURSE';node('p0-course-format').value='CHAPTER';
context.p0RealOrganizationOptions();
assert.equal(node('p0-real-organization-panel').hidden,false);
assert.equal(node('p0-organization').required,true);
assert.throws(()=>context.p0RealOrganizationSelection({course_format:'CHAPTER'}),/ORGANIZATION_REQUIRED/);
assert.match(node('p0-organization-note').textContent,/bloqué avant tout envoi/);
context.p0.courseOrganizations=[catalogue];
context.p0RealOrganizationOptions();
node('p0-program-notions').selectedOptions=[{value:'notion:test'}];
node('p0-organization-suggest').listeners.click();
assert.equal(node('p0-organization').value,catalogue.organization_id);
assert.equal(node('p0-organization').lastEvent,'change');
const selection=context.p0RealOrganizationSelection({course_format:'CHAPTER'});
assert.equal(selection.dossier_sha256,catalogue.dossier_sha256);
node('p0-real-organization').checked=false;
context.p0RealOrganizationOptions();
assert.equal(node('p0-organization').disabled,true);
assert.equal(context.p0RealOrganizationSelection({course_format:'CHAPTER'}),undefined);
node('p0-real-organization').checked=true;
node('p0-organization').value=catalogue.organization_id;
documentaryEnabled=true;
context.p0RealOrganizationOptions();
assert.equal(node('p0-organization').required,false);
assert.equal(node('p0-organization').disabled,true);
assert.equal(node('p0-real-organization-panel').hidden,true);
assert.equal(context.p0RealOrganizationSelection({course_format:'CHAPTER'}),undefined);
documentaryEnabled=false;
context.p0RealOrganizationOptions();
node('p0-organization').value=catalogue.organization_id;
(async()=>{
  await node('p0-organization-inspect').listeners.click();
  assert.equal(fetches,1);
  assert.ok(node('p0-organization-sources').children.some(c=>c.text===source.excerpt));
  assert.ok(node('p0-organization-sources').children.some(c=>c.text===source.title));
  const projected=context.p0RealSourceBlocks({organization_thread:{notice:'Synthetic notice',sources:[source]}});
  assert.ok(projected.some(b=>b.text.includes(source.source_url)));
  console.log('PASS: empty dossier refusal, exact selection, suggestion, read-only source view, source credits');
})().catch(error=>{console.error(error);process.exitCode=1;});
