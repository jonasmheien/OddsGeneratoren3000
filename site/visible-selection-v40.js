'use strict';
/* Display-only projection of the backend v40 final selection.
   Shared verbatim by browser and the v34 visibility archive. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.OddsVisibleV40=api;
})(typeof globalThis==='object'?globalThis:null,function(){
  const dayOf=d=>String(d?.editionDate||d?.localDate||'');
  const osloDay=date=>{
    const v=new Date(date);
    if(!Number.isFinite(+v))return '';
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(v);
    const all=Object.fromEntries(parts.map(p=>[p.type,p.value]));
    return `${all.year}-${all.month}-${all.day}`;
  };
  const kickoff=p=>+new Date(p?.kickoff);
  const upcoming=(p,edition,now)=>Number.isFinite(kickoff(p))&&kickoff(p)>+now&&
    osloDay(p.kickoff)===dayOf(edition)&&!!p.home&&!!p.away&&
    !!p.matchId&&!!p.market&&!!p.label&&Number.isFinite(Number(p.price))&&Number(p.price)>1;
  const groups=edition=>({safe:Array.isArray(edition?.safeBets)?edition.safeBets:[],
    high:Array.isArray(edition?.highRisk)?edition.highRisk:[],
    watch:Array.isArray(edition?.interestingObjects)?edition.interestingObjects:[]});
  const starts=edition=>Object.values(groups(edition)).flat().map(kickoff).filter(Number.isFinite);
  function shouldShowTomorrow(today,tomorrow,now){
    if(!tomorrow||tomorrow.previewEdition!==true||!/^\d{4}-\d\d-\d\d$/.test(dayOf(tomorrow)))return false;
    const local=osloDay(now);
    if(dayOf(tomorrow)<local || (today&&dayOf(today)>=dayOf(tomorrow)))return false;
    if(!today||dayOf(today)<local)return true;
    const a=starts(today);
    if(!a.length)return Number(new Intl.DateTimeFormat('en-GB',
      {timeZone:'Europe/Oslo',hour:'2-digit',hourCycle:'h23'}).format(now))>=18;
    return a.every(x=>x<=+now);
  }
  function selectEdition(today,tomorrow,now=new Date()){
    const useTomorrow=shouldShowTomorrow(today,tomorrow,now);
    let edition=useTomorrow?tomorrow:today;
    if(!edition&&tomorrow&&dayOf(tomorrow)>=osloDay(now))edition=tomorrow;
    if(!edition||!/^\d{4}-\d\d-\d\d$/.test(dayOf(edition)))return null;
    const future=starts(edition);
    const expired=dayOf(edition)<osloDay(now)||(!useTomorrow&&future.length>0&&future.every(x=>x<=+now));
    // v39 files predate backend authority. Never re-create bets in the client.
    const isAuthoritative=edition?.finalSelection?.version===40;
    const original=isAuthoritative?groups(edition):{safe:[],high:[],watch:[]};
    const selected=Object.fromEntries(Object.entries(original).map(([k,arr])=>[k,
      (expired?[]:arr.filter(p=>upcoming(p,edition,now))).slice(0,5)]));
    return {edition,groups:selected,expired,useTomorrow,day:dayOf(edition),
      authoritative:isAuthoritative,source:edition===tomorrow?'tomorrow':'today'};
  }
  return {dayOf,osloDay,upcoming,shouldShowTomorrow,selectEdition};
});
