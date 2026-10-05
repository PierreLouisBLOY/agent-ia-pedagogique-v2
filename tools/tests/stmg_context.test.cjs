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
function node(id) {return nodes[id] ||= {value:'',children:[],selectedOptions:[],listeners:{},addEventListener(type,callback){(this.listeners[type] ||= []).push(callback);},dispatch(type){for(const callback of this.listeners[type] || []) callback();},replaceChildren(){this.children=[];this.value='';this.selectedOptions=[];},append(x){this.children.push(x);}};}
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
const sgn = frames.find(frame=>frame.frame==='SGN_PREMIERE');
sgn.questions.push({question_ref:'question:SGN:unnumbered',label:'Comment organiser les activités ?',theme_ref:null});
node('level').value='FIRST_STMG';node('level').dispatch('change');
node('frame').value=sgn.program_version;node('frame').dispatch('change');
assert.equal(node('program-question').children.length,sgn.questions.length+1);
assert(node('program-question').children.some(option=>option.value==='question:SGN:unnumbered' && option.textContent.includes('thème à renseigner')));
node('program-question').value='question:SGN:unnumbered';node('program-question').dispatch('change');
assert.equal(node('capacities').children.length,0,'No unrelated capacity inherited');
assert(node('program-status').textContent.includes('Thème non renseigné'));
node('program-notions').selectedOptions=[{value:'notion:shared'}];node('depth').value='APPLICATION';
const unnumberedContext = sandbox.p0Context();
assert.equal(unnumberedContext.institutional.question_ref,'question:SGN:unnumbered');
assert.equal(unnumberedContext.institutional.theme_ref,null,'No invented official theme');
assert.equal(unnumberedContext.institutional.program_version,sgn.program_version);
node('level').value='BTS_CG_YEAR_2';node('discipline').value='Comptabilité et gestion';sandbox.p0InstitutionalOptions();
assert.throws(()=>sandbox.p0Context(),/P0_INSTITUTIONAL_CONTEXT_REQUIRED/);
assert.equal(node('discipline').value,'Comptabilité et gestion');
const bts={program_ref:'bts:frame',program_version:'bts:version',label:'BTS CG — référentiel',version_label:'UNIT',elements:[
  {id:'p:1',element_type:'PROCESS',parent_ref:null,official_label:'Processus 1'},
  {id:'a:1',element_type:'ACTIVITY',parent_ref:'p:1',official_code:'1.3',official_label:'Activité 1'},
  {id:'a:1.2',element_type:'ACTIVITY',parent_ref:'a:1',official_code:'1.3.2',official_label:'Sous-activité'},
  {id:'c:1',element_type:'COMPETENCY',parent_ref:'a:1.2',official_label:'Lettrer'},
  {id:'c:other',element_type:'COMPETENCY',parent_ref:'p:1',official_label:'Autre compétence'},
]};
sandbox.p0.institutionalCatalog.bts_frameworks=[bts];sandbox.p0InstitutionalOptions();
node('frame').value=bts.program_version;sandbox.p0InstitutionalQuestionOptions();
node('program-question').value='a:1.2';sandbox.p0InstitutionalCapacityOptions();
assert.deepEqual(node('capacities').children.map(n=>n.value),['c:1']);
node('capacities').selectedOptions=[{value:'c:1'}];node('program-notions').selectedOptions=[{value:'notion:shared'}];node('depth').value='APPLICATION';
const btsContext=sandbox.p0Context();assert.equal(btsContext.contract_id,'P0-CONTEXT-2.0');
assert.equal(btsContext.institutional.process_ref,'p:1');assert.equal(btsContext.institutional.activity_ref,'a:1.2');
assert.equal(btsContext.institutional.local_year,'BTS_CG_YEAR_2');assert(!('theme_ref' in btsContext.institutional));
assert(node('program-status').textContent.includes('progression locale'));
vm.runInContext(source.slice(source.indexOf('function p0Controls()'),source.indexOf('async function p0Fetch(')),sandbox);
sandbox.p0.prepared={context:{institutional_resolution:{status:'CONTENT_GAP'}}};sandbox.p0Controls();assert.equal(node('generate').disabled,true);
assert(!source.includes('proposed.level.includes("STMG") ? "Management"'));
const labels = [];
sandbox.uxNames = {};
sandbox.appendSearchText = (_, tag, text) => labels.push(text);
vm.runInContext(source.slice(source.indexOf('function uxContext('),source.indexOf('function uxQuality(')),sandbox);
for (const frame of frames) {
  labels.length=0;
  const specific=frame.program_component==='SPECIFIC';
  sandbox.uxContext({resource_type:'COURSE',level:frame.level,discipline:specific?'MSDGN — '+frame.specific_track:frame.label,
    institutional:{...frame,theme_ref:'theme:1',depth:'APPLICATION'},local_progression:{chapter:'Chapitre local'},
    institutional_resolution:{version_label:'UNIT-V1',question:{official_label:'1.1 Question'},capacities:[],notions:[],gaps:['UNIT_GAP']}});
  assert(labels.some(text=>text.startsWith('Niveau : ')));
  assert(labels.some(text=>text.startsWith('Enseignement : ')));
  assert(labels.some(text=>text.startsWith('Programme : ') && text.includes('UNIT-V1')));
  if(frame.program_component==='COMMON') assert(labels.includes('Partie : Enseignement commun'));
  if(specific) assert(labels.includes('Enseignement spécifique : '+frame.specific_track));
  assert(labels.includes('Progression locale : Chapitre local'));
}
labels.length=0;
sandbox.uxContext({...unnumberedContext,institutional_resolution:{version_label:'UNIT-V1',question:{official_label:'Comment organiser les activités ?'},gaps:['THEME_RELATIONSHIP_UNRESOLVED']}});
assert(labels.includes('Thème non renseigné · Comment organiser les activités ?'));
console.log('STMG_UI: seven frames, no Management default, exact programme/capacity selection, BTS compatibility, gap dispatch blocked PASS');
console.log('STMG_QUESTIONS: change events show unnumbered SGN questions, preserve exact identity and expose unresolved theme PASS');
labels.length=0;
sandbox.uxContext({...btsContext,institutional_resolution:{version_label:'UNIT',process:{official_label:'Processus 1'},activity:{official_label:'Activité 1'},competencies:[{official_label:'Lettrer'}],notions:[],gaps:[]}});
assert(labels.includes('Processus 1 · Activité 1'));assert(labels.includes('Compétences : Lettrer'));
assert(labels.some(t=>t.includes('progression locale')));assert(!labels.some(t=>t.startsWith('Thème')));
const savedStart=source.indexOf('function uxSavedCard(');
vm.runInContext(source.slice(savedStart,source.indexOf('document.querySelectorAll("[data-view]")',savedStart)),sandbox);
labels.length=0;
sandbox.uxSavedCard({record_sha256:'hidden',record:{view:{context:{...btsContext,institutional_resolution:{document_provenance:{title:'Référentiel admis'}}},references:[{}]},provenance:[],reviews:[],validations:[]}});
assert(labels.includes('Cadre institutionnel'));assert(labels.includes('Sources de contenu'));assert(labels.includes('Construction pédagogique'));
assert(labels.includes('Source institutionnelle distincte : Référentiel admis'));
assert(!labels.some(t=>t.includes('hidden') || t.includes('bts:version')));
console.log('BTS_UI: native activity/competency selection, year local, unresolved dispatch refused, saved three authority groups PASS');
