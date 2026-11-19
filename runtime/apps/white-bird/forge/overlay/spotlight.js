
/* ===================== الطائر الأبيض: Spotlight (Ctrl+K) =====================
   Quick search over open and saved chats, every app command and toggle, and the look; free text is sent as a request.
   It only clicks the app's own buttons, so it can't drift from the app logic. */
(function(){
  const $1=s=>document.querySelector(s);
  const norm=t=>(t||'').toLowerCase().replace(/[ً-ٰٟـ]/g,'').replace(/[أإآٱ]/g,'ا').replace(/ة/g,'ه').replace(/ى/g,'ي').replace(/\s+/g,' ').trim();
  const esc=t=>(t||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const box=document.createElement('div'); box.id='wbSpot';
  box.innerHTML='<div class="box" role="dialog" aria-label="بحث سريع"><div class="in">'+
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/></svg>'+
    '<input id="wbSpotIn" placeholder="دوّر على محادثة أو أمر، أو اكتب طلبك وابعته…" autocomplete="off" spellcheck="false"></div>'+
    '<div class="list" id="wbSpotList"></div><div class="ft"><span><kbd>↑</kbd> <kbd>↓</kbd> تنقّل</span><span><kbd>Enter</kbd> تنفيذ</span><span><kbd>Esc</kbd> قفل</span>'+
    '<span style="margin-inline-start:auto">الطائر الأبيض</span></div></div>';
  document.body.appendChild(box);
  const inp=box.querySelector('#wbSpotIn'), list=box.querySelector('#wbSpotList');
  let items=[], sel=0;
  const click=s=>()=>{const el=$1(s); if(el) el.click()};
  const on=s=>{const el=$1(s); return !!(el&&el.checked)};
  function catalog(){
    const A=[];
    document.querySelectorAll('#chats .ch').forEach(d=>{const n=d.querySelector('.nm');
      A.push({g:'المحادثات المفتوحة',t:(n?n.textContent:'').trim()||'محادثة',e:'💬',k:d.classList.contains('act')?'الحالية':'',run:()=>d.click()})});
    document.querySelectorAll('#saved .ch').forEach(d=>{const n=d.querySelector('.nm'),m=d.querySelector('.meta');
      A.push({g:'المحادثات المحفوظة',t:(n?n.textContent:'').trim(),e:'🕘',k:m?m.textContent.trim():'',run:()=>d.click()})});
    [['محادثة جديدة','✚','#newBtn','Ctrl N'],['محادثة جديدة بدون ذاكرة','🫥','#zeroBtn'],['اسأل كل المحادثات مرة واحدة','🧠','#allBtn'],
     ['اختار مجلد الشغل','📁','#dirBtn'],['إرفاق ملفات','📎','#attBtn'],['رسالة صوتية','🎤','#micBtn','Ctrl M'],['مهام جاهزة','⚡','#tasksBtn'],
     ['المهارات والمكتبة والمستودعات','🧩','#skBtn'],['ربط محادثات بالمحادثة دي','🔗','#linkBtn'],['الوكلاء المساعدين','🤖','#teamBtn'],
     ['المعاينة','🎬','#pvBtn'],['لوحة الملفات','📂','#fBtn'],['تصدير المحادثة','⤓','#expBtn','Ctrl E'],['إيقاف الشغل الحالي','⏹','#stopBtn','Esc'],
     ['الإعدادات: المفتاح والموديل والإضافات','⚙','#setBtn'],['العرض وأحجام اللوحات','🪟','#viewBtn']
    ].forEach(([t,e,s,k])=>{const el=$1(s); if(el&&!(s==='#stopBtn'&&el.style.display==='none')) A.push({g:'أوامر',t,e,k:k||'',run:click(s)})});
    [['تحليل عميق بـ REA','🔬','#deep'],['تحكم في الكمبيوتر كله وكروم','🖥','#ctl'],['قارن موديلات','🧪','#cmp'],['عقل الطائر','🧠','#brainChk'],
     ['اعرض التفكير','💭','#thinkChk'],['سحابة Higgsfield المجانية','☁','#cloudChk'],['أدوات التحليل','🧰','#reChk'],['موافقة تلقائية على الأوامر','✓','#auto']
    ].forEach(([t,e,s])=>{if($1(s)) A.push({g:'مفاتيح المحادثة',t:(on(s)?'اقفل: ':'شغّل: ')+t,e,k:on(s)?'شغّال ●':'مقفول ○',run:click(s),toggle:1})});
    [['مظهر فاتح','☀','#themeRow [data-t=light]'],['مظهر غامق','🌙','#themeRow [data-t=dark]'],['مظهر تلقائي مع ويندوز','◐','#themeRow [data-t=auto]'],
     ['وضع التركيز (الشات بس)','◎','#vFocus','F11'],['تكبير الخط','A+','#viewPop [data-z="+"]','Ctrl +'],['تصغير الخط','A−','#viewPop [data-z="-"]','Ctrl −']
    ].forEach(([t,e,s,k])=>{if($1(s)) A.push({g:'المظهر',t,e,k:k||'',run:click(s)})});
    return A;
  }
  function score(it,q){
    if(!q) return it.g==='أوامر'||it.g==='المحادثات المفتوحة'?1:0;
    const h=norm(it.t+' '+it.g), toks=q.split(' ');
    if(!toks.every(w=>h.includes(w))) return 0;
    const p=norm(it.t).indexOf(toks[0]); return (p===0?3:p>0?2:1)-(it.toggle?0.5:0);   // a tie never puts a switch first
  }
  function render(){
    const raw=inp.value.trim(), q=norm(raw), all=catalog();
    items=all.map(it=>({it,s:score(it,q)})).filter(x=>x.s>0).sort((a,b)=>b.s-a.s).map(x=>x.it).slice(0,40);
    if(raw) items.push({g:'اطلب من الطائر',t:'ابعت: «'+raw+'»',e:'🕊',k:'Enter',ask:raw},{g:'اطلب من الطائر',t:'حطها في خانة الكتابة بس',e:'✎',k:'',fill:raw});
    if(sel>=items.length) sel=0;
    let g='', h='';
    items.forEach((it,i)=>{ if(it.g!==g){g=it.g; h+='<div class="g">'+esc(g)+'</div>'}
      h+='<div class="it2'+(i===sel?' on':'')+'" data-i="'+i+'"><span class="e">'+esc(it.e)+'</span><span class="t">'+esc(it.t)+'</span><span class="k">'+esc(typeof it.k==='string'?it.k:'')+'</span></div>'});
    list.innerHTML=h||'<div class="none">اكتب أي حاجة…</div>';
    const cur=list.querySelector('.it2.on'); if(cur) cur.scrollIntoView({block:'nearest'});
  }
  function run(i){
    const it=items[i]; if(!it) return; close();
    if(it.ask!=null||it.fill!=null){const t=$1('#inp'); if(!t) return; t.value=it.ask!=null?it.ask:it.fill; t.dispatchEvent(new Event('input',{bubbles:true}));
      t.focus(); if(it.ask!=null){const b=$1('#sendBtn'); if(b) b.click()} return}
    setTimeout(()=>it.run(),0);
  }
  function open(){box.classList.add('on'); inp.value=''; sel=0; render(); setTimeout(()=>inp.focus(),0)}
  function close(){box.classList.remove('on')}
  window.wbSpotlight={open,close};
  inp.addEventListener('input',()=>{sel=0;render()});
  inp.addEventListener('keydown',e=>{
    if(e.key==='ArrowDown'){e.preventDefault();sel=Math.min(sel+1,items.length-1);render()}
    else if(e.key==='ArrowUp'){e.preventDefault();sel=Math.max(sel-1,0);render()}
    else if(e.key==='Enter'){e.preventDefault();run(sel)}
    else if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close()}
  });
  list.addEventListener('mousemove',e=>{const d=e.target.closest('.it2'); if(d&&+d.dataset.i!==sel){sel=+d.dataset.i;render()}});
  list.addEventListener('click',e=>{const d=e.target.closest('.it2'); if(d) run(+d.dataset.i)});
  box.addEventListener('mousedown',e=>{if(e.target===box) close()});
  document.addEventListener('keydown',e=>{
    if(e.ctrlKey&&!e.shiftKey&&!e.altKey&&(e.code==='KeyK'||e.keyCode===75||e.key==='k'||e.key==='K')){e.preventDefault();e.stopPropagation();box.classList.contains('on')?close():open()}
  },true);
  // Esc closes the settings sheet like a macOS sheet (and never reaches the «stop the work» shortcut while it does)
  document.addEventListener('keydown',e=>{
    if(e.key!=='Escape'||box.classList.contains('on')) return;
    const m=$1('#modal'); if(m&&getComputedStyle(m).display!=='none'){e.preventDefault();e.stopPropagation();const c=$1('#closeM'); if(c) c.click(); else m.style.display='none'}
  },true);
  const btn=$1('#wbSpotBtn'); if(btn) btn.onclick=open;
})();
