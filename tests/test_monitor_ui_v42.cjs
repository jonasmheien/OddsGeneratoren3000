'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const s=fs.readFileSync('site/three-fields-v26.js','utf8');
const html=fs.readFileSync('site/index.html','utf8');
assert.doesNotMatch(s,/get\('quality-v42'\)|get\('performance-v42'\)|tf-monitor|tf-qualified/);
for(const asset of ['three-fields-v26.js','three-fields-v26.css','hitrate-v51.js'])assert.ok(html.includes(asset));
for(const asset of ['sportsbook-v37.js','market-radar-v39.js','quality-v20.js','versions-v22.js'])assert.ok(!html.includes(asset));
assert.doesNotMatch(html,/edition-indicator|DAGENS UTGAVE|type="search"/);
console.log('PASS: three categories and statistics without duplicate dashboards or diagnostics');
