'use strict';
/* v1.5: Market families remain visible, even when optional feeds have no quotes.
   'Til vurdering' is never represented as a confirmed betting recommendation. */
(() => {
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const groups = [
    ['goals','Over / under mål'],['team_goals','Lagmål'],['btts','Begge lag scorer'],
    ['first_half','1. omgang'],['corners','Hjørnespark'],['cards','Kort'],['goalscorer','Målscorer'],
  ];
  const groupLabel = Object.fromEntries(groups);
  const odds = n => Number(n).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  const time = value => { const d = new Date(value); return Number.isNaN(+d)?'':new Intl.DateTimeFormat('nb-NO',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Oslo'}).format(d); };
  const permittedImage = url => { try {const u=new URL(url);return u.protocol==='https:'&&['crests.football-data.org','upload.wikimedia.org'].includes(u.hostname)?u.href:null;}catch{return null;} };
  const familyOf = code => {
    code=String(code||'');
    if(code.startsWith('CO'))return 'corners';
    if(code.startsWith('CA'))return 'cards';
    if(code.startsWith('GS:'))return 'goalscorer';
    if(code.startsWith('TH')||code.startsWith('TA'))return 'team_goals';
    if(code.startsWith('H1'))return 'first_half';
    if(code.startsWith('BTTS'))return 'btts';
    if(/^[OU](15|25|35)$/.test(code))return 'goals';
    return null;
  };
  let host, active='all', snapshot=null;
  function ensure(){
    if(host)return host;
    host=document.createElement('section');host.id='spesialmarkeder';host.className='extra-market-section';
    host.setAttribute('aria-labelledby','special-market-heading');
    host.innerHTML='<div class="extra-heading"><div><div class="extra-kicker">ODDS OG SPILLMARKEDER</div><h2 id="special-market-heading">Flere spillmarkeder</h2></div></div><div id="market-filters" class="market-filters" role="group" aria-label="Filtrer spillmarkeder"></div><div id="extra-market-body"></div>';
    const before=document.querySelector('#resultater');
    if(before)before.before(host); else document.querySelector('main')?.appendChild(host);
    host.querySelector('#market-filters').addEventListener('click', event=>{
      const target=event.target.closest('button[data-family]');if(!target)return;
      active=target.dataset.family; if(snapshot)render(snapshot);
    });
    return host;
  }
  function badge(name,url,approved){
    const initials=String(name||'?').split(/\s+/).filter(Boolean).slice(0,2).map(s=>s[0]).join('').toUpperCase()||'?';
    const src=approved?permittedImage(url):null;
    return `<span class="extra-team-mark" aria-hidden="true">${src?`<img src="${esc(src)}" loading="lazy" alt="">`:esc(initials)}</span>`;
  }
  function collect(data){
    const opts=data?.additionalMarkets||{};
    const matches=new Map((data?.matches||[]).map(m=>[String(m.id),m]));
    const seen=new Set(), out=[];
    function add(p,qualified){
      if(!p || !Number.isFinite(Number(p.price)) || Number(p.price)<=1 || !p.label)return;
      const kind=p.marketType||familyOf(p.market);if(!kind||!groupLabel[kind])return;
      const key=String(p.matchId)+'|'+String(p.market);if(seen.has(key))return;seen.add(key);
      const fixture=matches.get(String(p.matchId))||{};
      out.push({...p,marketType:kind,verified:qualified,homeCrest:p.homeCrest||fixture.homeCrest,awayCrest:p.awayCrest||fixture.awayCrest});
    }
    for(const key of ['recommendations','safeBets','highRisk'])for(const p of (data?.[key]||[]))add(p,true);
    for(const p of (opts.tips||[]))add(p,true);
    for(const p of (opts.watchlist||[]))add(p,false);
    return out;
  }
  function card(p,approved){
    const good=p.verified===true;
    const reasons=(Array.isArray(p.rationale)?p.rationale:[]).filter(s=>typeof s==='string').slice(0,5);
    const probability=Number(p.probability);
    const probLine=Number.isFinite(probability) && probability>0 && probability<1
      ?`<span class="market-prob">Modellanslag: ${Math.round(100*probability)} %</span>`:'';
    return `<details class="extra-market-card ${good?'market-good':'market-watch'}">
      <summary><span class="extra-market-main"><span class="extra-market-league">${esc(p.league||'Fotball')} · ${esc(time(p.kickoff))}</span>
        <span class="extra-market-match">${badge(p.home,p.homeCrest,approved)}${esc(p.home)} <span class="market-vs">–</span> ${badge(p.away,p.awayCrest,approved)}${esc(p.away)}</span>
        <span class="extra-market-play">${esc(p.label)}</span></span>
        <span class="extra-market-right"><strong>${esc(odds(p.price))}</strong><span>${good?'ANALYSERT':'TIL VURDERING'}</span></span></summary>
      <div class="extra-market-analysis"><p>${good?'Dette utfallet passerte analysekravene ved publisering. Modellsannsynligheten er ikke kalibrert.':'Bookmakerprisen er tilgjengelig, men utfallet er ikke godkjent som et anbefalt spill.'}</p>${probLine}
        ${reasons.length?`<ul>${reasons.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
        <span class="extra-market-source">${esc(p.oddsSource||p.source||'The Odds API')} · pris ved analyse${p.bookmakers?' · '+esc(p.bookmakers)+' bookmakere':''}</span></div></details>`;
  }
  function render(data){
    snapshot=data;ensure();
    const extra=data?.additionalMarkets;
    const all=collect(data);
    const filters=[['all','Alle',all.length],...groups.map(([key,label])=>[key,label,all.filter(p=>p.marketType===key).length])];
    $('market-filters').innerHTML=filters.map(([key,label,count])=>`<button type="button" data-family="${key}" aria-pressed="${String(active===key)}" class="market-filter${active===key?' selected':''}">${esc(label)} <span>${count}</span></button>`).join('');
    const shown=active==='all'?groups.filter(([key])=>all.some(p=>p.marketType===key)):groups.filter(([key])=>key===active);
    const approved=data?.visualAssets?.licensedCrests===true;
    let body='';
    if(!extra){body+='<p class="market-status">Dagens analyse ble publisert før de nye markedene ble hentet. Ordinære målspill kan vises nedenfor. De øvrige markedsdataene blir tilgjengelige etter en ny dagsanalyse.</p>';}
    else if(extra.issues?.length){body+='<p class="market-status">Noen spesialmarkeder kunne ikke hentes i dag. Eksisterende tips påvirkes ikke.</p>';}
    if(!shown.length)body+='<div class="extra-market-empty">Ingen tilgjengelige odds i de valgte markedene. Velg en kategori for å se statusen.</div>';
    for(const [key,label] of shown){
      const allForGroup=all.filter(p=>p.marketType===key);
      const top=allForGroup.filter(x=>x.verified).slice(0,3);
      const watch=allForGroup.filter(x=>!x.verified).slice(0,4);
      const count=top.length+watch.length;
      body+=`<div class="market-family"><div class="market-family-title"><strong>${esc(label)}</strong><span>${count?`${count} viste utfall`:'Ingen dokumenterte odds'}</span></div>`;
      if(count){body+=`<div class="extra-market-grid">${[...top,...watch].map(p=>card(p,approved)).join('')}</div>`;}
      else{body+=`<div class="extra-market-empty">${!extra?'Ikke analysert med denne versjonen ennå.':'Ingen verifiserbare odds eller tilstrekkelig grunnlag i dagens utgave.'}</div>`;}
      body+='</div>';
    }
    body+='<p class="extra-market-footnote">Over/under-markeder kan ha ulike linjer og oppgjørsregler hos bookmakerne. Målscorere krever kontroll av startoppstilling. Fravær av odds eller statistikk gir ingen spillanbefaling.</p>';
    $('extra-market-body').innerHTML=body;
    host.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.replaceWith(document.createTextNode('?'));},{once:true}));
  }
  async function load(){
    try{const response=await fetch(`data/today.json?markets_v15=${Date.now()}`,{cache:'no-store'});if(response.ok)render(await response.json());}
    catch{/* this secondary display cannot block the main pick list */}
  }
  document.addEventListener('DOMContentLoaded',()=>{ensure();load();$('refresh-data')?.addEventListener('click',load);setInterval(()=>{if(document.visibilityState==='visible')load();},60000);});
})();
