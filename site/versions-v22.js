'use strict';
/* Read-only, source-faithful version history and illustrative combinations.
   Never claim median odds are jointly available at one bookmaker. */
(() => {
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const amount = n => Number(n).toLocaleString('nb-NO', {minimumFractionDigits:2,maximumFractionDigits:2});
  const dated = s => {let d = new Date(s);return Number.isFinite(+d)?d.toLocaleString('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit',day:'numeric',month:'short'}):String(s||'–');};
  function mount(){
    if(document.getElementById('og-v22'))return document.getElementById('og-v22');
    const section=document.createElement('section');section.id='og-v22';section.className='q20-root';
    const main=document.querySelector('main');if(!main)return null;
    main.append(section);return section;
  }
  function combinations(snapshot){
    const now=Date.now();
    const picks=(snapshot.recommendations||[]).filter(p=>Number.isFinite(+p.price)&&+p.price>1&&
      p.matchId&&p.market&&Date.parse(p.kickoff)>now+15*60000&&
      Number.isFinite(+p.conservativeEdge)&&+p.conservativeEdge>=.02);
    if(picks.length<2)return '';
    const combos=[];
    for(const preferred of [false,true]){
      const sorted=[...picks].sort((a,b)=>preferred
        ? (Number(a.price)-Number(b.price)) : (Number(b.conservativeEdge)-Number(a.conservativeEdge)));
      const used=new Set(),legs=[];
      for(const p of sorted){if(used.has(String(p.matchId)))continue;
        used.add(String(p.matchId));legs.push(p);if(legs.length===3)break;}
      if(legs.length>=2 && !combos.some(c=>c.legs.map(p=>p.matchId+'|'+p.market).join()===legs.map(p=>p.matchId+'|'+p.market).join()))
        combos.push({name:preferred?'Lavere odds':'Høyere beregnet verdi',legs});
    }
    if(!combos.length)return '';
    const inner=combos.map(c=>{
      const product=c.legs.reduce((n,p)=>n*Number(p.price),1);
      return `<article class="q20-card"><strong>${esc(c.name)}</strong><ul>${c.legs.map(p=>`<li>${esc(p.home)} – ${esc(p.away)}: ${esc(p.label)} (${amount(p.price)})</li>`).join('')}</ul>
      <p>Matematisk produkt av observerte medianodds: <strong>${amount(product)}</strong></p></article>`;
    }).join('');
    return `<section aria-labelledby="v22-combo-title"><div class="q20-heading"><div><span class="q20-kicker">EKSPERIMENTELL KOMBINASJON</span><h2 id="v22-combo-title">Kupongutkast</h2><p>Kun fra kvalifiserte spill i ulike kamper.</p></div></div><div class="q20-grid">${inner}</div><p class="q20-sub">Ikke spillbare eller verifiserte kuponger. Medianoddsen kan komme fra ulike bookmakere, og samlet odds må kontrolleres manuelt hos én tilbyder.</p></section>`;
  }
  function revisions(list){
    if(!Array.isArray(list)||!list.length)return '';
    return `<section aria-labelledby="v22-revisions-title" style="margin-top:32px"><div class="q20-heading"><div><span class="q20-kicker">SPORBARE ENDRINGER</span><h2 id="v22-revisions-title">Tidligere versjoner</h2><p>Ved ny analyse av samme dag bevares forrige versjon.</p></div></div><div class="q20-grid">${list.slice(0,6).map(r=>`<article class="q20-card"><strong>${esc(r.date)} · ${esc(dated(r.after))}</strong><p class="q20-explain">${(r.added||[]).length} nye · ${(r.removed||[]).length} utgåtte · ${(r.repriced||[]).length} endrede odds</p>
    ${(r.removed||[]).length ? `<details class="q20-details"><summary>Utgåtte tips</summary><ul>${r.removed.map(p=>`<li>${esc(p.home)} – ${esc(p.away)} · ${esc(p.label)}: ${esc(p.reason)}</li>`).join('')}</ul></details>`:''}</article>`).join('')}</div></section>`;
  }
  async function render(){
    try{
      const [a,b]=await Promise.all([fetch('data/today.json?t='+Date.now(),{cache:'no-store'}),
        fetch('data/versions.json?t='+Date.now(),{cache:'no-store'})]);
      if(!a.ok)return;
      const snap=await a.json(),versions=b.ok?await b.json():[];
      const holder=mount();if(!holder)return;
      const content=combinations(snap)+revisions(versions);
      holder.innerHTML=content;
      holder.hidden=!content;
    }catch(e){/* The existing site remains usable when v2.2 data is missing. */}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    render();document.getElementById('refresh-data')?.addEventListener('click',render);
    setInterval(()=>{if(document.visibilityState==='visible')render();},60000);
  });
})();
