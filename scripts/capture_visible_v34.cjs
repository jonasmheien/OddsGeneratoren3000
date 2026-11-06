'use strict';
/**
 * Snapshot the exact candidate ranking already used by the published v33 UI.
 * Diagnostic only: does NOT qualify, change, settle, or publish a new tip.
 * Official results are NOT inferred from fixtures/odds by this tool.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');
const visibleV40=require('../site/visible-selection-v40.js');

const ANCHOR = "  document.addEventListener('DOMContentLoaded',()=>{";
const GROUPS = ['high', 'safe', 'watch'];
const stableHash = obj => crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex').slice(0,24);
function localDay(date) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
}
function getPicker(){
  // Deprecated interface retained for callers. Never evaluates frontend code.
  return {dayOf:visibleV40.dayOf,selectEdition:visibleV40.selectEdition};
}
function selectAsDisplayed(today,tomorrow,_picker,now){
  // The published UI and archive invoke precisely the same pure projection.
  return visibleV40.selectEdition(today,tomorrow,now);
}
const numeric = v => v !== '' && v !== undefined && v !== null && Number.isFinite(Number(v)) ? Number(v) : null;
function noVigMarketChance(match, market, at){
  const codes=['H','U','B'].includes(market)?['H','U','B']:
    ['O25','U25'].includes(market)?['O25','U25']:
    ['O35','U35'].includes(market)?['O35','U35']:[];
  if(!match || !codes.length || !codes.every(code=>{
    const q=match.odds?.[code];
    const time=Date.parse(q?.lastUpdated), age=at.getTime()-time;
    const price=numeric(q?.price),books=numeric(q?.books ?? q?.bookmakers);
    return price!==null && price>=1.05 && price<=25 && books!==null&&books>=3&&
      Number.isFinite(time)&&age>=-120000&&age<=18*3600000;
  })) return null;
  const inverse=codes.map(code=>1/Number(match.odds[code].price));
  const total=inverse.reduce((a,b)=>a+b,0);
  if(total<.98||total>1.27)return null;
  return (1/Number(match.odds[market].price))/total;
}
function inspect(p, group, edition, at) {
  const match=(edition.matches||[]).find(x=>x && String(x.id)===String(p.matchId));
  const q=match?.odds?.[p.market] || null;
  const matchForm = key => {
    const s=String(match?.[key] || p[key] || '').trim();
    return /^[WDL]{1,20}$/.test(s) ? s.slice(0,5) : '';
  };
  const formHome=matchForm('formHome'),formAway=matchForm('formAway');
  const model=match?.model || null;
  const sample=Array.isArray(model?.sample) && model.sample.length===2 ? model.sample.map(numeric) : null;
  const modelChance=numeric(model?.probabilities?.[p.market]);
  const quotedAt=String(p.oddsUpdatedAt || q?.lastUpdated || '');
  const quoteTimestamp=Date.parse(quotedAt);
  const quoteFresh=Number.isFinite(quoteTimestamp) && quoteTimestamp >= at.getTime()-18*3600000 && quoteTimestamp <= at.getTime()+120000;
  const matchingQuote=numeric(q?.price);
  const listedPrice=numeric(p.price);
  const priceMatches=matchingQuote!==null && listedPrice!==null && Math.abs(matchingQuote-listedPrice)<0.025;
  const books=numeric(p.bookmakers ?? q?.books);
  const fullForm=formHome.length===5&&formAway.length===5;
  const modelHistory=sample&&sample.every(x=>x!==null&&x>=5);
  const sourceType=p._candidateType==='market'?'bookmaker_market':p._candidateType==='model'?'form_model':group==='watch'?'observation':'qualified_model';
  const issues=[];
  if (!formHome.length) issues.push('home_form_missing');
  else if (formHome.length<5) issues.push('home_form_under_five');
  if (!formAway.length) issues.push('away_form_missing');
  else if (formAway.length<5) issues.push('away_form_under_five');
  if (!model) issues.push('model_unavailable');
  else if (!modelHistory) issues.push('model_sample_under_five');
  if (!quoteFresh) issues.push('quote_outdated_or_missing');
  if (!priceMatches) issues.push('quote_mismatch_or_missing');
  if (books===null||books<3) issues.push('few_quoting_bookmakers');
  const marketChance=noVigMarketChance(match,p.market,at);
  if(modelChance!==null && marketChance!==null && Math.abs(modelChance-marketChance)>=.20)
    issues.push('form_model_market_gap_over_20_percentage_points');
  const sourcePredictions=Array.isArray(match?.predictions)?match.predictions:[];
  const sourcedExpert=Boolean((p.expertReason&&p.expertSource)||sourcePredictions.some(x=>typeof x.reason==='string'&&x.reason.trim()&&typeof x.source==='string'&&x.source.trim()));
  // Match the visible compact analysis exactly; keep its probability provenance.
  let probability=null,probabilitySource='not_available';
  const recorded=numeric(p.probability),conservative=numeric(p.conservativeProbability);
  if(group!=='watch' && !p._candidateType && conservative!==null){
    probability=conservative;probabilitySource='uncalibrated_conservative_scenario';
  }else if(p._candidateType==='market'){
    probability=recorded;probabilitySource='no_vig_bookmaker_market';
  }else if(modelChance!==null){
    probability=modelChance;probabilitySource='uncalibrated_form_model';
  }else if(recorded!==null && p._candidateType==='model'){
    probability=recorded;probabilitySource='uncalibrated_form_model';
  }else if(match){
    probability=noVigMarketChance(match,p.market,at);
    if(probability!==null)probabilitySource='no_vig_bookmaker_market';
  }
  if(probability===null||probability<0||probability>1)probability=null;
  const rating=fullForm&&modelHistory&&modelChance!==null?'form_and_model':
    (formHome.length||formAway.length)?'partial_form':'odds_only';
  return {
    matchId:String(p.matchId),home:String(p.home||''),away:String(p.away||''),league:String(p.league||''),
    kickoff:String(p.kickoff||''),market:String(p.market||''),label:String(p.label||''),
    price:listedPrice,probability,probabilitySource,quotedAt,
    bookmakerCount:books,sourceType,
    result:{status:'not_verified'},
    quality:{evidenceTier:rating,homeLastFive:formHome,awayLastFive:formAway,
      modelSample:sample,formModelProbability:modelChance,bookmakerImpliedProbability:marketChance,
      quoteFresh,quoteMatchesListing:priceMatches,
      independentlySourcedWrittenExpert:sourcedExpert,
      issues},
  };
}
function archiveSnapshot(root,{now=new Date()}={}) {
  if (!Number.isFinite(+now)) throw new Error('Valid clock required');
  const todayPath=path.join(root,'site/data/today.json');
  const tomorrowPath=path.join(root,'site/data/tomorrow.json');
  if(!fs.existsSync(todayPath))throw new Error('Missing published today.json');
  const today=JSON.parse(fs.readFileSync(todayPath,'utf8'));
  const tomorrow=fs.existsSync(tomorrowPath)?JSON.parse(fs.readFileSync(tomorrowPath,'utf8')):null;
  const selected=selectAsDisplayed(today,tomorrow,null,now);
  if (!selected) return {changed:false,reason:'no_edition'};
  const {edition,groups,expired}=selected;
  const n=GROUPS.reduce((sum,key)=>sum+groups[key].length,0);
  if (!n) return {changed:false,reason:expired?'edition_expired':'no_visible_candidates'};
  const day=visibleV40.dayOf(edition);
  if(day<localDay(now))return {changed:false,reason:'historical_edition'};
  const records=Object.fromEntries(GROUPS.map(group=>[group,groups[group].map(p=>inspect(p,group,edition,now))]));
  const all=GROUPS.flatMap(k=>records[k]);
  if(all.some(p=>!p.matchId||!p.market||!p.home||!p.away||!p.kickoff||!(p.price>1)))
    throw new Error('Invalid entry; snapshot not archived');
  const id=stableHash({day,generatedAt:edition.generatedAt,records});
  const location=path.join(root,'state','tip-audit-v34',day+'.json');
  const old=fs.existsSync(location)?JSON.parse(fs.readFileSync(location,'utf8')):null;
  if(old && (old.schemaVersion!==34||old.editionDate!==day||!Array.isArray(old.revisions)))throw new Error('Existing journal has unknown schema');
  if(old?.revisions.some(r=>r.id===id))return {changed:false,reason:'already_archived',day,id};
  const summary={total:n,high:records.high.length,safe:records.safe.length,watch:records.watch.length,
    withBothFive:all.filter(p=>p.quality.homeLastFive.length===5&&p.quality.awayLastFive.length===5).length,
    withFormModel:all.filter(p=>p.quality.evidenceTier==='form_and_model').length,
    marketBased:all.filter(p=>p.sourceType==='bookmaker_market').length,
    expertWritten:all.filter(p=>p.quality.independentlySourcedWrittenExpert).length,
    modelMarketConflicts:all.filter(p=>p.quality.issues.includes('form_model_market_gap_over_20_percentage_points')).length,
    unverifiedResults:n};
  const revision={id,editionGeneratedAt:edition.generatedAt||null,recordedAt:now.toISOString(),summary,groups:records};
  const journal=old||{schemaVersion:34,editionDate:day,revisions:[]};
  journal.revisions.push(revision);
  const publicReport={schemaVersion:34,editionDate:day,revisionId:id,
    editionGeneratedAt:revision.editionGeneratedAt,recordedAt:revision.recordedAt,
    summary,notes:[
      'Records are exactly the preselected backend v40 objects visible in the shared frontend projection at capture time.',
      'Percentages are not historically calibrated. Bookmaker-based percentages are not independent forecasts.',
      'Result status is unverified until matched to an authoritative final score; no wins/losses are inferred.',
    ]};
  const reportPath=path.join(root,'site','data','tip-audit-v34.json');
  atomicJson(location,journal);
  atomicJson(reportPath,publicReport);
  return {changed:true,day,id,summary,file:location};
}
function atomicJson(file,value) {
  fs.mkdirSync(path.dirname(file),{recursive:true});
  const tmp=file+'.tmp';
  fs.writeFileSync(tmp,JSON.stringify(value,null,2)+'\n','utf8');
  fs.renameSync(tmp,file);
}
if (require.main===module){
  const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
  try{
    const result=archiveSnapshot(root);
    console.log('TIP_AUDIT_V34 '+JSON.stringify(result));
    if(process.env.GITHUB_OUTPUT)fs.appendFileSync(process.env.GITHUB_OUTPUT,`changed=${result.changed?'true':'false'}\n`);
  }catch(err){
    console.error('TIP_AUDIT_V34_ERROR '+err.stack);
    process.exitCode=1;
  }
}
module.exports={archiveSnapshot,inspect,getPicker,selectAsDisplayed};
