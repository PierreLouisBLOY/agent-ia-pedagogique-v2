"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync("frontend/app.js", "utf8");
const code = source.slice(source.indexOf("function proposePreparation("), source.indexOf("function uxContext("));
const sandbox = {}; vm.createContext(sandbox); vm.runInContext(code, sandbox);
for (const [phrase, family, level] of [
  ["Un cours première STMG sur les organisations", "COURSE", "FIRST_STMG"],
  ["Un exercice BTS CG deuxième année sur le coût", "EXERCISE", "BTS_CG_YEAR_2"],
  ["Questions ouvertes terminale STMG sur la performance", "OPEN_QUESTIONS", "FINAL_STMG"],
  ["QCM BTS CG 1 sur le lettrage", "QCM", "BTS_CG_YEAR_1"],
  ["Quiz terminale STMG sur le management", "QUIZ", "FINAL_STMG"],
  ["Une évaluation BTS CG 2 sur le BFR, durée 60 minutes, noté sur 20", "ASSESSMENT", "BTS_CG_YEAR_2"]
]) {
  const result = sandbox.proposePreparation(phrase);
  assert.equal(result.family, family); assert.equal(result.level, level); assert.equal(result.ambiguities.length, 0);
}
const ambiguous = sandbox.proposePreparation("Cours ou quiz BTS CG sur la TVA");
assert.equal(ambiguous.family, ""); assert.equal(ambiguous.level, ""); assert.equal(ambiguous.ambiguities.length, 2);
assert.equal(sandbox.proposePreparation("Évaluation BTS CG 2 sur le BFR de 1 heure notée sur 20").duration, 60);
assert.equal(sandbox.proposePreparation("x".repeat(501)).objective, "");
assert(!source.includes("localStorage")); assert(!source.includes("innerHTML"));
const html = fs.readFileSync("frontend/index.html", "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(ids.length, new Set(ids).size);
for (const key of ["preparation-composer", "production-card", "sources-drawer", "session-conversations"]) assert(ids.includes(key));
console.log("CONVERSATION_SHELL: 6 families, 4 levels, ambiguity, duration, length, safe DOM, closed storage, unique IDs PASS");
