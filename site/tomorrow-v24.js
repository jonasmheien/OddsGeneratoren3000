'use strict';
/* Tomorrow's preview stays separate from the canonical daily edition. */
(() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const localDate = () => {
    const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Oslo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const fields=Object.fromEntries(parts.map(p=>[p.type,p.value]));
    return `${fields.year}-${fields.month}-${fields.day}`;
  };
  const dateLabel = value => {
    const day = new Date(value + 'T12:00:00+01:00');
    if (Number.isNaN(+day)) return escape(value);
    return new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',day:'numeric',month:'long'}).format(day);
  };
  const kickoffTime = value => {
    const date = new Date(value);
    if (Number.isNaN(+date)) return '–';
    return new Intl.DateTimeFormat('nb-NO',{timeZone:'Europe/Oslo',hour:'2-digit',minute:'2-digit'}).format(date);
  };
  const fmtPrice = value => Number(value).toLocaleString('nb-NO',{minimumFractionDigits:2,maximumFractionDigits:2});
  let section;
  function card(p){
    const tag = p.category === 'safe' ? 'Safe Bet' : p.category === 'high' ? 'High Risk' : 'Dagens tips';
    return `<article class="tomorrow-card">
      <div class="tomorrow-league">${escape(p.league || 'Fotball')} · ${escape(kickoffTime(p.kickoff))} · ${escape(tag)}</div>
      <div class="tomorrow-match">${escape(p.home)} <span>–</span> ${escape(p.away)}</div>
      <div class="tomorrow-market"><span>${escape(p.label)}</span><strong>${escape(fmtPrice(p.price))}</strong></div>
      <p>${escape((p.rationale || [])[0] || 'Foreløpig anbefaling. Odds og verdi må kontrolleres på nytt.')}</p>
    </article>`;
  }
  async function refresh(){
    try {
      const response = await fetch(`data/tomorrow.json?v=${Date.now()}`,{cache:'no-store'});
      if(!response.ok){if(section)section.hidden=true;return;}
      const obj = await response.json();
      if(!obj.previewEdition || !/^\d{4}-\d{2}-\d{2}$/.test(obj.editionDate) || obj.editionDate < localDate()){
        if(section)section.hidden=true;return;
      }
      // Once the morning's official edition exists, the preview disappears.
      // From midnight until then it is still shown, clearly labelled preliminary.
      try {
        const actual=await fetch(`data/today.json?v=${Date.now()}`,{cache:'no-store'});
        if(actual.ok){
          const edition=await actual.json();
          if((edition.editionDate || edition.localDate || '') >= obj.editionDate){
            if(section)section.hidden=true;return;
          }
        }
      }catch{}
      if(!section){
        const anchor=document.querySelector('#dagens'); if(!anchor)return;
        section=document.createElement('section');section.id='morgendagen';section.className='tomorrow-section';
        anchor.before(section);
      }
      const eligible=(Array.isArray(obj.recommendations)?obj.recommendations:[]).filter(p=>p && p.home && p.away && p.market && Number(p.price)>1);
      const more=eligible.length>5?`<p class="tomorrow-extra">${eligible.length-5} flere kvalifiserte spill i forhåndsanalysen.</p>`:'';
      const observations=Number(obj.qualityAudit?.observations ?? obj.observations?.length ?? 0);
      // Show real bookmaker-quoted games even when no independent team history
      // supports a recommendation. Never relabel a quote as a qualified pick.
      const quoted=(Array.isArray(obj.matches)?obj.matches:[])
        .filter(m => m && m.home && m.away && m.kickoff && m.odds && Object.keys(m.odds).length)
        .sort((a,b) => String(a.kickoff).localeCompare(String(b.kickoff)));
      const matchesHtml=quoted.length?`<div class="tomorrow-quoted-title">${quoted.length} kamper med registrerte bookmakerodds</div>
        <div class="tomorrow-quoted-list">${quoted.slice(0,16).map(m=>`<div class="tomorrow-quoted-game"><span>${escape(m.home)} – ${escape(m.away)}</span><small>${escape(m.league)} · ${escape(kickoffTime(m.kickoff))}</small></div>`).join('')}</div>
        ${quoted.length>16?`<p class="tomorrow-extra">${quoted.length-16} flere kamper med odds inngår i analysen.</p>`:''}`:'';
      section.innerHTML=`<div class="tomorrow-heading"><div><div class="tomorrow-kicker">FORHÅNDSANALYSE</div><h2>Tips for ${escape(dateLabel(obj.editionDate))}</h2></div><div class="tomorrow-count">${eligible.length} kvalifiserte</div></div>
        <p class="tomorrow-intro">Analysert på forhånd med tilgjengelige bookmakerodds. Spill kan endre seg før kampstart. Ny kontroll utføres i morgen kl. 09:17.</p>
        ${eligible.length?`<div class="tomorrow-grid">${eligible.slice(0,5).map(card).join('')}</div>${more}`:
         `<p class="tomorrow-empty">Ingen kvalifiserte spill ennå: det mangler tilstrekkelig uavhengig statistikk eller dokumentert verdi. ${observations} markeder er markert for observasjon.</p>`}
        ${matchesHtml}`;
      section.hidden=false;
    } catch {if(section)section.hidden=true;}
  }
  document.addEventListener('DOMContentLoaded',()=>{
    refresh();document.getElementById('refresh-data')?.addEventListener('click',refresh);
    setInterval(()=>{if(document.visibilityState==='visible')refresh();},90000);
  });
})();
