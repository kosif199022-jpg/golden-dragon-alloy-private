
const PLAN = __PLAN__;
function rng(seed){let s=seed>>>0;return()=>{s=(s*1664525+1013904223)>>>0;return s/4294967296;};}
const ease = {
  out:(x)=>1-Math.pow(1-x,3), inOut:(x)=>x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2,
  back:(x)=>{const c=1.70158;return 1+(c+1)*Math.pow(x-1,3)+c*Math.pow(x-1,2);}
};
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const scenes=[...document.querySelectorAll('[data-shot]')];
const R=rng(PLAN.seed||7); const dots=[...Array(40)].map(()=>({x:R(),y:R(),r:2+R()*6}));
const TR=.45;
function enter(el,kind,p){
  const e=ease.out(p);
  el.style.opacity=kind==='cut'?1:(kind==='fade'||kind==='zoom'?e:1);
  el.style.clipPath=kind==='wipe'?`inset(0 ${(1-e)*100}% 0 0)`:'none';
  el.style.transform=kind==='zoom'?`scale(${1.25-.25*e})`:kind==='slide'?`translateY(${(1-e)*12}%)`:'none';
}
function drawShot(i,local,len){
  const s=PLAN.shots[i], el=scenes[i], u=clamp(local/len);
  const words=el.querySelectorAll('.w');
  words.forEach((w,k)=>{const p=clamp((local-.15-k*.12)/.5);w.style.opacity=p;w.style.transform=`translateY(${(1-ease.back(p))*40}px)`;});
  const shape=el.querySelector('.shape');
  if(shape){const a=ease.inOut(u);shape.style.transform=`rotate(${a*180}deg) scale(${.6+.6*a})`;shape.style.borderRadius=`${50-40*a}%`;}
  const field=el.querySelector('.field');
  if(field){field.innerHTML='';dots.forEach(d=>{const n=document.createElement('i');n.style.left=(d.x*100)+'%';n.style.top=((d.y+u*.3)%1*100)+'%';n.style.width=n.style.height=d.r+'px';field.appendChild(n);});}
}
window.__kosif={duration:PLAN.duration,seek(t){
  PLAN.shots.forEach((s,i)=>{
    const el=scenes[i], on=t>=s.start-1e-9&&(t<s.end||i===PLAN.shots.length-1);
    el.style.visibility=on?'visible':'hidden';
    if(on){enter(el,s.transition_in,clamp((t-s.start)/TR));drawShot(i,t-s.start,s.end-s.start);}
  });
}};
window.__kosif.seek(0);
