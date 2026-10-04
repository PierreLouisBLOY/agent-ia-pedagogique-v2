// Execute the actual transport helper against stalled headers and stalled bodies.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../frontend/app.js'), 'utf8');
const helper = source.slice(source.indexOf('async function localBoundedRequest('), source.indexOf('async function conversationFetch('));

async function check(mode) {
  let calls = 0, deadline;
  const pending = signal => new Promise((resolve, reject) => {
    if (signal.aborted) reject(new Error('ABORTED'));
    else signal.addEventListener('abort', () => reject(new Error('ABORTED')));
  });
  const context = {AbortController, setTimeout: callback => {deadline = callback; return 1;}, clearTimeout: () => {},
    fetch: async (url, options) => {
      calls++;
      assert.equal(url, '/local'); assert.equal(options.method, 'POST');
      if (mode === 'headers') return pending(options.signal);
      return {json: () => mode === 'body' ? pending(options.signal) : Promise.resolve({state:'OK'})};
    }};
  vm.createContext(context); vm.runInContext(helper, context);
  const result = context.localBoundedRequest('/local', {method:'POST'}, response => response.json());
  await Promise.resolve(); await Promise.resolve();
  if (mode === 'success') assert.equal((await result).state, 'OK');
  else {deadline(); await assert.rejects(result, /ABORTED/);}
  assert.equal(calls, 1, 'A stalled command must never retry automatically');
}
(async () => {for (const mode of ['success','headers','body']) await check(mode); console.log('3 transport checks PASS');})().catch(error => {console.error(error); process.exitCode=1;});
