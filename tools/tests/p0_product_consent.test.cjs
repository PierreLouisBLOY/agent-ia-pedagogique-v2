// Exercise the shipped consent state and click handlers with an explicit local double.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const {test} = require("node:test");
const source = fs.readFileSync(path.join(__dirname, "../../frontend/app.js"), "utf8");
function harness() {
  const nodes = new Map();
  const node = id => {if (!nodes.has(id)) nodes.set(id, {checked:false,hidden:true,children:[],
    replaceChildren(){this.children=[];}, addEventListener(event,callback){this[event]=callback;}});
    return nodes.get(id);};
  const prepared = {preparation_ref:"prep:"+"a".repeat(32), preparation_sha256:"b".repeat(64)};
  const consent = {state:"LOCAL_OPERATOR_CONSENT_REQUIRED",provider_attempts:0,review_state:"NOT_RUN",
    source_status:"RESERVE",consent_actor:"LOCAL_OPERATOR_DELEGATED",preview_sha256:"c".repeat(64),
    transfer_destination:{provider:"OPENAI",model:"gpt-5.6-terra",endpoint:"https://api.openai.com/v1/responses",
      permission_sha256:"1".repeat(64)},
    remaining_calls:2,remaining_budget_usd:"0.28",preview:{schema:"P0-PRODUCT-CONSENT-PREVIEW-1.0",
      ...prepared,permission_sha256:"1".repeat(64),request_sha256:"d".repeat(64),request_bytes:200,cost_bound_usd:"0.100000",
      request_body_utf8:JSON.stringify({model:"gpt-5.6-terra",max_output_tokens:4096,store:false,stream:false,background:false}),
      source_receipts:[{reference:{source_ref:"synthetic:source"},authority:"UNKNOWN"}],
      expires_at_utc:new Date(Date.now()+600000).toISOString()}};
  const calls=[],mutations=[];
  const context = {Date,JSON,Number,Array,Error,URL,undefined,p0:{prepared,normalConsentBinding:"EXPLICIT_PRODUCT_PERMISSION",consent:null},
    p0Element:node,p0Command:()=>"e".repeat(32),p0Controls:()=>{},p0Render:(view)=>{context.rendered=view;},
    appendSearchText:(parent,tag,text)=>parent.children.push({tag,text}),
    p0Run:async(action,mutation)=>{mutations.push(mutation);await action();},
    p0Fetch:async(route,body)=>{calls.push({route,body});return route.endsWith("consent-preview") ? consent :
      {state:"CANDIDATE",view:{version_ref:"ver:"+"f".repeat(32)},publication:{state:"APPLICATION_SAVED"}};}};
  vm.createContext(context);
  const start = source.indexOf("function p0ClearConsent(");
  const end = source.indexOf('p0Element("teacher").addEventListener',start);
  vm.runInContext(source.slice(start,end),context);
  return {context,node,prepared,consent,calls,mutations};
}
test("preview and checkbox changes never dispatch; exact explicit consent dispatches once",async()=>{
  const h=harness();
  await h.node("generate").click();
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].route,"/api/v2/p0/consent-preview");
  assert.equal(h.mutations[0],false);
  assert.equal(h.node("consent-transfer").checked,false);assert.equal(h.node("consent-cost").checked,false);
  assert.equal(h.node("consent").hidden,false);
  h.node("consent-transfer").checked=true;h.node("consent-transfer").change();
  await assert.rejects(h.node("consent-send").click(),/P0_CONSENT_REQUIRED/);
  assert.equal(h.calls.length,1);
  h.node("consent-cost").checked=true;h.node("consent-cost").change();
  assert.equal(h.calls.length,1);
  await h.node("consent-send").click();
  assert.equal(h.calls.length,2);assert.equal(h.calls[1].route,"/api/v2/p0/consent-generate");
  assert.deepEqual(JSON.parse(JSON.stringify(h.calls[1].body)),{command_id:"e".repeat(32),...h.prepared,
    preview_sha256:"c".repeat(64),transfer_accepted:true,cost_bound_accepted:true});
  assert.equal(h.context.p0.consent,null);assert.equal(h.context.p0.prepared,null);
  await assert.rejects(h.node("consent-send").click(),/P0_CONSENT_REQUIRED/);
  assert.equal(h.calls.length,2,"No replay of consumed preview");
  assert.match(h.node("status").textContent,/conservée dans votre bibliothèque/);
});
test("expired, rebound, untrusted and out-of-budget previews are refused without dispatch",()=>{
  for(const mutate of [c=>c.preview.preparation_ref="prep:"+"f".repeat(32),
    c=>c.preview.expires_at_utc="2000-01-01T00:00:00Z",c=>c.preview.cost_bound_usd="0.140001",
    c=>c.preview.cost_bound_usd="NaN",c=>c.provider_attempts=1,c=>c.preview_sha256="unknown",
    c=>c.preview.source_receipts=[]]) {
    const h=harness();mutate(h.consent);
    assert.equal(h.context.p0ConsentMatches(h.consent,h.prepared),false);
    assert.throws(()=>h.context.p0ConsentPreview(h.consent,h.prepared),/P0_CONSENT_PREVIEW_BINDING/);
    assert.equal(h.calls.length,0);
  }
});
test("cancel clears the exact body and consent without changing the preparation",async()=>{
  const h=harness();await h.node("generate").click();h.node("consent-cancel").click();
  assert.equal(h.context.p0.consent,null);assert.equal(h.node("consent").hidden,true);
  assert.equal(h.context.p0.prepared,h.prepared);assert.equal(h.calls.length,1);
  assert.equal(h.node("consent-summary").children.length,0);
});

test("destination is displayed exactly from the validated permission projection",async()=>{
  const h=harness();await h.node("generate").click();
  assert.equal(h.context.p0TransferDestination(h.consent,h.consent.preview),h.consent.transfer_destination);
  assert.equal(h.node("consent-summary").children[0].text,
    "OpenAI · gpt-5.6-terra · https://api.openai.com/v1/responses");
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].route,"/api/v2/p0/consent-preview");
});
const destinationMutants = [
  ["missing",c=>delete c.transfer_destination],
  ["null",c=>c.transfer_destination=null],
  ["array",c=>c.transfer_destination=[]],
  ["extra field",c=>c.transfer_destination.official=true],
  ["missing field",c=>delete c.transfer_destination.model],
  ["provider",c=>c.transfer_destination.provider="ANTHROPIC"],
  ["model",c=>c.transfer_destination.model="other"],
  ["hash",c=>c.transfer_destination.permission_sha256="2".repeat(64)],
  ["preview permission",c=>c.preview.permission_sha256="2".repeat(64)],
  ["missing preview permission",c=>delete c.preview.permission_sha256],
  ["invalid permission",c=>c.transfer_destination.permission_sha256="bad"],
  ["non-string endpoint",c=>c.transfer_destination.endpoint=1],
  ...["http://api.openai.com/v1/responses","https://example.org/v1/responses",
      "https://api.openai.com/v1/responses/input_tokens","https://api.openai.com:444/v1/responses",
      "https://api.openai.com:443/v1/responses","https://user@api.openai.com/v1/responses",
      "https://user:pass@api.openai.com/v1/responses","https://api.openai.com/v1/responses?x=1",
      "https://api.openai.com/v1/responses?","https://api.openai.com/v1/responses#x",
      "https://api.openai.com/v1/responses#","https://API.OPENAI.COM/v1/responses",
      "https://api.openai.com/v1/responses/","not a url",""].map(endpoint=>[
        "endpoint " + endpoint,c=>c.transfer_destination.endpoint=endpoint])
];
for (const [label,mutate] of destinationMutants) test("destination refuses " + label + " before dispatch",async()=>{
  const h=harness();mutate(h.consent);
  assert.equal(h.context.p0ConsentMatches(h.consent,h.prepared),false);
  assert.throws(()=>h.context.p0ConsentPreview(h.consent,h.prepared),/P0_CONSENT_PREVIEW_BINDING/);
  assert.equal(h.calls.length,0);
  h.context.p0.consent=h.consent;
  h.node("consent-transfer").checked=h.node("consent-cost").checked=true;
  await assert.rejects(h.node("consent-send").click(),/P0_CONSENT_REQUIRED/);
  assert.equal(h.calls.length,0);
});
