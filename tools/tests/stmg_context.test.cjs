const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const frames = [
  ['MANAGEMENT_PREMIERE','FIRST_STMG','PREMIERE','MANAGEMENT','SPECIALITE',null,'Management'],
  ['SGN_PREMIERE','FIRST_STMG','PREMIERE','SCIENCES_GESTION_NUMERIQUE','SPECIALITE',null,'Sciences de gestion et numérique'],
  ...['COMMON','GF','MERCATIQUE','RHC','SIG'].map(track => ['MSDGN_'+track,'FINAL_STMG','TERMINALE','MSDGN',track==='COMMON'?'COMMON':'SPECIFIC',track==='COMMON'?null:track,'MSDGN '+track]),
].map(([frame,level,education_level,teaching_subject,program_component,specific_track,label]) => ({frame,level,education_level,teaching_subject,program_component,specific_track,label,
  program_ref:'program:'+frame,program_version:'version:'+frame,version_label:'UNIT-V1',authority:'UNATTESTED',
  questions:[{question_ref:'question:'+frame,label:'1.1 Question '+frame,theme_ref:'theme:1'}],
  capacities:[{capacity_ref:'capacity:'+frame,label:'Capacité '+frame,question_ref:'question:'+frame}]}));
const nodes = {};
function node(id) {return nodes[id] ||= {value:'',children:[],selectedOptions:[],addEventListener(){},replaceChildren(){this.children=[];this.value='';},append(x){this.children.push(x);}};}
const sandbox={p0:{institutionalCatalog:{frames,notions:[{notion_ref:'notion:shared',label:'Notion partagée'}]},view:null,busy:false,uncertain:false,nonce:'unit',liveBinding:'EXPLICIT_PORT'},
  p0Element:node,document:{createElement:()=>node('new-'+Math.random()),getElementById:node}};
vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('function p0Context()'),source.indexOf('p0Element("family").addEventListener')),sandbox);
node('family').value='COURSE';node('topics').value='Notion partagée';node('objectives').value='Expliquer';node('difficulty').value='STANDARD';
for(const frame of frames){
  node('level').value=frame.level;sandbox.p0InstitutionalOptions();
  assert.equal(node('frame').children[0].value,'','No implicit subject selection');
  assert.equal(node('discipline').value,'');
  assert.throws(()=>sandbox.p0Context(),/P0_INSTITUTIONAL_CONTEXT_REQUIRED/);
  node('frame').value=frame.program_version;sandbox.p0InstitutionalQuestionOptions();
  node('program-question').value=frame.questions[0].question_ref;sandbox.p0InstitutionalCapacityOptions();
  assert.equal(node('capacities').children.length,1);
  assert.equal(node('capacities').children[0].value,'capacity:'+frame.frame);
  node('depth').value='APPLICATION';node('program-notions').selectedOptions=[{value:'notion:shared'}];node('capacities').selectedOptions=[{value:'capacity:'+frame.frame}];
  const context=sandbox.p0Context();assert.equal(context.contract_id,'P0-CONTEXT-2.0');
  assert.equal(context.institutional.program_ref,frame.program_ref);assert.equal(context.institutional.program_version,frame.program_version);
  assert.equal(context.institutional.teaching_subject,frame.teaching_subject);assert.equal(context.institutional.specific_track,frame.specific_track);
  assert.equal(context.institutional_resolution,null);assert.equal(context.discipline,frame.label);
}
node('level').value='BTS_CG_YEAR_2';node('discipline').value='Comptabilité et gestion';sandbox.p0InstitutionalOptions();
assert.equal(sandbox.p0Context().contract_id,'R6-P0-CONTEXT-1.0');assert.equal(node('discipline').value,'Comptabilité et gestion');
vm.runInContext(source.slice(source.indexOf('function p0Controls()'),source.indexOf('async function p0Fetch(')),sandbox);
sandbox.p0.prepared={context:{institutional_resolution:{status:'CONTENT_GAP'}}};sandbox.p0Controls();assert.equal(node('generate').disabled,true);
assert(!source.includes('proposed.level.includes("STMG") ? "Management"'));
console.log('STMG_UI: seven frames, no Management default, exact programme/capacity selection, BTS compatibility, gap dispatch blocked PASS');
