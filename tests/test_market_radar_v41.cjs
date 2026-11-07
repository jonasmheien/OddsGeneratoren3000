'use strict';
const assert=require('node:assert/strict');
const {sameFixture}=require('../site/market-radar-v39.js');
const kickoff='2026-11-07T17:30:00Z';
function match(home,away){return {home,away,kickoff};}
const aliases=[
 [['Stuttgart','Bremen'],['VfB Stuttgart','Werder Bremen']],
 [['Preston NE','Southampton'],['Preston North End','Southampton']],
 [['Blackburn','West Ham'],['Blackburn Rovers','West Ham United']],
 [['Mainz','Bayern'],['FSV Mainz 05','Bayern Munich']],
 [['QPR','Lincoln City'],['Queens Park Rangers','Lincoln City']]
];
for(const [a,b] of aliases) assert.ok(sameFixture(match(...a),match(...b)),a.join(' v '));
assert.ok(!sameFixture(match('Preston NE','Southampton'),match('Preston NE','West Ham')));
console.log('PASS: v41 radar provider aliases, no unrelated teams merged');
