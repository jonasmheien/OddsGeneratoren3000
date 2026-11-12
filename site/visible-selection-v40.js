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
  // Defensive fail-closed projection; backend remains the only tip selector.
  // Covers known fixture-provider aliases in already published preview data.
  const knownAliases={
    hsv:'hamburgersv',hamburgsv:'hamburgersv',mgladbach:'monchengladbach',
    borussiamgladbach:'monchengladbach',borussiamonchengladbach:'monchengladbach',
    boltonwanderers:'bolton',silkeborgif:'silkeborg',fczwolle:'zwolle',peczwolle:'zwolle',
    sevillafc:'sevilla',blackburnrovers:'blackburn',westhamunited:'westham',
    vfbstuttgart:'stuttgart',werderbremen:'bremen',prestonnorthend:'prestonne',
    fsvmainz05:'mainz',bayernmunich:'bayern',norwichcity:'norwich',stokecity:'stoke',
    wrexhamafc:'wrexham',wolverhamptonwanderers:'wolverhampton',
    birminghamcity:'birmingham',cardiffcity:'cardiff',charltonathletic:'charlton',
    sheffieldunited:'sheffieldutd',queensparkrangers:'qpr',
    westbromwichalbion:'westbrom',nottinghamforest:'nottingham',
    manchestercity:'mancity',tottenhamhotspur:'tottenham',
    czechia:'czechrepublic',turkiye:'turkey',republicofireland:'ireland'
  };
  const team=name=>{
    const norm=String(name||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'')
      .toLowerCase().replace(/[^a-z0-9]/g,'');
    return knownAliases[norm]||norm;
  };
  const fixtureIdentity=p=>{
    const home=team(p?.home),away=team(p?.away);
    const day=osloDay(p?.kickoff);
    return home&&away&&day?`${day}|${home}|${away}`:null;
  };
  const kickoff=p=>+new Date(p?.kickoff);
  const upcoming=(p,edition,now)=>Number.isFinite(kickoff(p))&&kickoff(p)>+now&&
    osloDay(p.kickoff)===dayOf(edition)&&!!p.home&&!!p.away&&
    !!p.matchId&&!!p.market&&!!p.label&&Number.isFinite(Number(p.price))&&Number(p.price)>1;
  const groups=edition=>({
    qualified:edition?.finalSelection?.rankedRecommendations===true&&Array.isArray(edition?.recommendations)
      ?edition.recommendations.filter(p=>p?.qualificationTier==='qualified'):[],
    safe:Array.isArray(edition?.safeBets)?edition.safeBets:[],
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
    const original=isAuthoritative?groups(edition):{qualified:[],safe:[],high:[],watch:[]};
    // Never show the same real match twice, even in older v40 preview JSON.
    // This only removes invalid duplicates, never creates or promotes bets.
    const selected={qualified:[],safe:[],high:[],watch:[]},seen=new Set();
    for(const group of ['qualified','safe','high','watch']){
      for(const p of (expired?[]:original[group])){
        if(!upcoming(p,edition,now))continue;
        const identity=fixtureIdentity(p);
        if(!identity||seen.has(identity))continue;
        if(group!=='qualified'&&selected[group].length>=5)break;
        seen.add(identity);
        selected[group].push(p);
      }
    }
    return {edition,groups:selected,expired,useTomorrow,day:dayOf(edition),
      authoritative:isAuthoritative,source:edition===tomorrow?'tomorrow':'today'};
  }
  return {dayOf,osloDay,upcoming,fixtureIdentity,shouldShowTomorrow,selectEdition};
});
