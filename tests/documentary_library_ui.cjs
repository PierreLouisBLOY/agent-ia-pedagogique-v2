const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const nodes=new Map(),ready=[];
function make(){return {value:'',checked:true,hidden:true,children:[],listeners:{},
 replaceChildren(...xs){this.children=xs;},append(...xs){this.children.push(...xs);},
 addEventListener(t,f){this.listeners[t]=f;},querySelectorAll(q){return this.boxes||[];}};}
function node(id){if(!nodes.has(id))nodes.set(id,make());return nodes.get(id);}
let requests=0,invalidations=0;
const catalogue={archive_sha256:'a'.repeat(64),snapshot_sha256:'b'.repeat(64),
 organizations:[{id:'DECATHLON',label:'DECATHLON'},{id:'ORANGE',label:'ORANGE'}],
 documents:[{id:'D07',organization_id:'DECATHLON',title:'SYNTHETIC culture'},
 {id:'O05',organization_id:'ORANGE',title:'SYNTHETIC values'}]};
const context={document:{getElementById:node,addEventListener(t,f){ready.push(f);},createElement:make,createTextNode:t=>({text:t})},
 p0Element:id=>node('p0-'+id),Option:function(text,value){return {text,value};},
 p0Invalidate(){invalidations++;},p0RealOrganizationOptions(){},p0Run:f=>f(),
 appendSearchText:(out,tag,text)=>out.children.push({tag,text}),
 p0Fetch:async url=>{requests++;assert.equal(url,'/api/v2/p0/documentary-library/D07');return {
 snapshot_sha256:catalogue.snapshot_sha256,document:{id:'D07',metadata:{title:'SYNTHETIC culture',rights_policy:'local'},
 blocks:[{kind:'PARAGRAPH',text:'<script>literal synthesis</script>'}]},
 sources:[{id:'S1',publisher:'Synthetic',title:'Primary',url:'https://example.org/source',rights_status:'None inferred'}]};}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/documentary-library.js'),'utf8'),context);
ready.forEach(f=>f());node('p0-family').value='COURSE';node('p0-course-format').value='CHAPTER';
context.p0DocumentaryConfigure(catalogue);
assert.equal(node('p0-documentary-panel').hidden,false);
assert.equal(node('p0-real-organization-panel').hidden,true);
assert.throws(()=>context.p0DocumentarySelection({course_format:'CHAPTER'}),/Choisissez/);
node('p0-documentary-organization').value='DECATHLON';node('p0-documentary-organization').listeners.change();
assert.equal(node('p0-documentary-documents').children.length,1);assert.equal(invalidations,1);
node('p0-documentary-documents').boxes=[{value:'D07'}];
assert.equal(context.p0DocumentarySelection({course_format:'CHAPTER'}).document_ids[0],'D07');
node('p0-documentary-documents').boxes=Array.from({length:7},(_,i)=>({value:'D'+i}));
assert.throws(()=>context.p0DocumentarySelection({course_format:'CHAPTER'}),/Choisissez/);
(async()=>{await context.p0DocumentaryInspect('D07');assert.equal(requests,1);
 assert.ok(node('p0-documentary-read').children.some(x=>x.text==='<script>literal synthesis</script>'));
 node('p0-documentary-enabled').checked=false;
 assert.equal(context.p0DocumentarySelection({course_format:'CHAPTER'}),undefined);
 console.log('PASS: 2 groups, explicit selection, six-document bound, invalidation, read-only inspection and literal text');
})().catch(e=>{console.error(e);process.exitCode=1;});
