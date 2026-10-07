import {importRegisters,validateProject} from './formats.mjs';
import {compile,validateRows,wav,HZ,RATE} from './synth.mjs';
const $=s=>document.getElementById(s),clone=o=>JSON.parse(JSON.stringify(o)),KEY='speech2ay-ay-workshop-v1';
const requestedPreset=new URLSearchParams(location.search).get('preset');
const storageKey=()=>KEY;
function soundInfo(){
 for(const o of [...$('preset').options])if(!presets.some(p=>p.id===o.value)&&o.value!==state.preset)o.remove();
 document.querySelector('h1').textContent='Shape your AY sound.';
 $('soundHint').textContent=`${state.rows.length} frames · ${(state.rows.length/HZ).toFixed(2)} seconds. Edit speech, effects or tone/noise sequences. Shared noise and envelope settings affect all enabled channels.`;
}
let presets=[],state,base,history=[],future=[],track='pitch',selection=[0,1],samples=null,buffer=null,baselineBuffer=null;
let ctx,gainNode,sourceNode,sourceGain,started=0,offset=0,playing=false,baselinePlaying=false,loopBounds=[0,1];
let serial=0,latest=0,timer=null,wantPlay=false,dirty=false,pointer=null,hover=0,liveCurve=null,playSerial=0;
const tracks=[];
function add(id,label,min,max,help,get,set,options={}){tracks.push({id,label,min,max,help,get,set,...options});}
add('pitch','All voices · pitch',50,150,'100% keeps the starting pitch. Draw above 100 to raise it, below to lower it. Noise and hardware-envelope pitch have their own curves.',(s,i)=>s.pitch[i],(s,i,v)=>s.pitch[i]=Math.round(v*10)/10,{unit:'%',group:'Sound'});
add('noise','Noise period',1,31,'Lower numbers make brighter noise; higher numbers make darker noise. Noise must be enabled on at least one channel below.',(s,i)=>s.rows[i][6],(s,i,v)=>s.rows[i][6]=Math.round(v),{group:'Sound'});
for(let c=0;c<3;c++){
 const ch='ABC'[c];
 add('vol'+c,`Volume ${ch}`,0,16,'0 = silent; 1–15 = fixed AY levels; 16 = use the shared hardware envelope. Drawing a fixed level replaces envelope mode on those frames.',(s,i)=>s.rows[i][8+c],(s,i,v)=>s.rows[i][8+c]=Math.round(v),{group:'Levels'});
 add('freq'+c,`Tone ${ch} · frequency`,27,110250,'Frequency in Hz before the All voices pitch curve. Logarithmic scale. Its tone switch below must be on to hear this pitch.',(s,i)=>110250/Math.max(1,s.rows[i][2*c]+256*s.rows[i][2*c+1]),(s,i,v)=>{const p=Math.max(1,Math.min(4095,Math.round(110250/v)));s.rows[i][2*c]=p&255;s.rows[i][2*c+1]=p>>8;},{log:true,unit:'Hz',group:'Individual pitch'});
 for(const [kind,bit] of [['tone',c],['noise',c+3]])add(kind+c,`${ch} · ${kind} on/off`,0,1,'1 = enabled, 0 = disabled. A channel can combine tone and noise. Both disabled produces a constant level, not silence; use volume 0 to mute.',(s,i)=>+( !(s.rows[i][7]&(1<<bit)) ),(s,i,v)=>{if(Math.round(v))s.rows[i][7]&=~(1<<bit);else s.rows[i][7]|=1<<bit;},{group:'Routing'});
}
add('envPeriod','Envelope period',1,65535,'Shared hardware-envelope period. Lower is faster. A channel uses it when its volume is 16. This can create a buzz at short periods.',(s,i)=>Math.max(1,s.rows[i][11]+256*s.rows[i][12]),(s,i,v)=>{const p=Math.round(v);s.rows[i][11]=p&255;s.rows[i][12]=p>>8;},{log:true,advanced:true});
add('envShape','Envelope shape / restart',-1,15,'−1 = continue without restarting. 0–15 writes an AY shape and restarts the envelope on that frame. 8 repeats a decay, 10 is triangular, 12 repeats a rise. Draw −1 first, then set a shape on one frame to start it.',(s,i)=>s.rows[i][13]===255?-1:s.rows[i][13],(s,i,v)=>s.rows[i][13]=Math.round(v)<0?255:Math.round(v),{advanced:true});
const def=()=>tracks.find(t=>t.id===track),duration=()=>state.rows.length/HZ;
function message(s){$('status').textContent=s;}
function project(){return {version:1,preset:state.preset,current:clone(state),baseline:clone(base),selection:[...selection],track};}
function autosave(){try{localStorage.setItem(storageKey(state.preset),JSON.stringify(project()));}catch{message('Browser storage unavailable. Use Save project to keep edits.');}}
function snapshot(){history.push(clone(state));if(history.length>60)history.shift();future=[];buttons();}
function buttons(){$('undo').disabled=!history.length;$('redo').disabled=!future.length;$('exportWav').disabled=dirty||!samples;}
function change(){latest=++serial;dirty=true;buttons();autosave();draw();clearTimeout(timer);timer=setTimeout(rebuild,90);}
function renderJob(rows){const id=++serial;latest=id;worker.postMessage({id,rows});}
function rebuild(){clearTimeout(timer);try{message('Rendering…');renderJob(compile(state.rows,state.pitch));}catch(e){message(e.message);}}
const worker=new Worker('./worker.mjs',{type:'module'});
worker.onerror=e=>message('Audio renderer error: '+e.message);
worker.onmessage=({data})=>{
 if(data.id!==latest)return;
 if(data.error){message(data.error);return;}
 samples=data.samples;buffer=null;dirty=false;buttons();
 const resume=playing&&!baselinePlaying,at=playhead();
 if(resume||wantPlay){wantPlay=false;startPlayback(false,resume?at:selection[0]);}
 message(`Ready · ${state.rows.length} frames · ${Math.round(data.ms)} ms render`);draw();
};
async function audio(){if(!ctx){ctx=new AudioContext();gainNode=ctx.createGain();gainNode.gain.value=+$('gain').value;gainNode.connect(ctx.destination);}await ctx.resume();}
function makeBuffer(x){const b=ctx.createBuffer(1,x.length,RATE);b.copyToChannel(x,0);return b;}
function halt(){playSerial++;wantPlay=false;if(sourceNode){try{sourceNode.stop();}catch{}sourceNode=null;}playing=false;baselinePlaying=false;$('play').textContent='▶ Play edits';draw();}
function playhead(){if(!playing||!ctx)return selection[0];const elapsed=ctx.currentTime-started+offset;if($('loop').checked)return loopBounds[0]+((elapsed-loopBounds[0])%(loopBounds[1]-loopBounds[0])+(loopBounds[1]-loopBounds[0]))%(loopBounds[1]-loopBounds[0]);return Math.min(loopBounds[1],elapsed);}
async function startPlayback(original=false,at=selection[0]){
 const ticket=++playSerial;await audio();if(ticket!==playSerial)return;
 if(!original&&(dirty||!samples)){wantPlay=true;rebuild();return;}
 if(original&&!baselineBuffer){
  // Keep main editing renderer independent of the reference render.
  message('Rendering starting version…');const w=new Worker('./worker.mjs',{type:'module'});
  try{const x=await new Promise((resolve,reject)=>{w.onmessage=({data})=>data.error?reject(Error(data.error)):resolve(data.samples);w.onerror=e=>reject(Error(e.message));w.postMessage({id:1,rows:compile(base.rows,base.pitch)});});baselineBuffer=makeBuffer(x);}catch(e){message(e.message);return;}finally{w.terminate();}
 }
 if(ticket!==playSerial)return;
 if(!original&&!buffer)buffer=makeBuffer(samples);
 const old=sourceNode,oldGain=sourceGain,now=ctx.currentTime;
 if(old){old.onended=null;oldGain.gain.setValueAtTime(oldGain.gain.value,now);oldGain.gain.linearRampToValueAtTime(0,now+.012);try{old.stop(now+.013);}catch{}}
 sourceNode=ctx.createBufferSource();sourceNode.buffer=original?baselineBuffer:buffer;
 sourceGain=ctx.createGain();sourceGain.gain.setValueAtTime(0,now);sourceGain.gain.linearRampToValueAtTime(1,now+.012);sourceNode.connect(sourceGain);sourceGain.connect(gainNode);
 loopBounds=[...selection];at=Math.max(selection[0],Math.min(at,selection[1]-.001));offset=at;started=now;
 sourceNode.loop=$('loop').checked;sourceNode.loopStart=selection[0];sourceNode.loopEnd=selection[1];
 sourceNode.start(now,at);if(!sourceNode.loop)sourceNode.stop(now+selection[1]-at);
 const own=sourceNode;own.onended=()=>{if(sourceNode===own){playing=false;sourceNode=null;$('play').textContent='▶ Play edits';draw();}};
 playing=true;baselinePlaying=original;$('play').textContent='↻ Play edits';message(original?'Playing starting version':'Playing edits');
}
function fields(){const t=def();$('curve').value=track;$('curveTitle').textContent=t.label;$('help').textContent=t.help;$('value').min=t.min;$('value').max=t.max;$('value').value=Math.round(t.get(state,Math.min(hover,state.rows.length-1))*10)/10;$('value').step=t.id==='pitch'?'.1':'1';$('smooth').disabled=t.max-t.min<=1||t.id==='envShape';document.querySelectorAll('[data-track]').forEach(b=>b.classList.toggle('active',b.dataset.track===track));}
function syncSelection(){const d=duration();selection=selection.map(v=>Math.max(0,Math.min(d,v)));if(selection[1]-selection[0]<1/HZ){selection[1]=Math.min(d,selection[0]+1/HZ);selection[0]=Math.max(0,selection[1]-1/HZ);}$('from').max=d;$('to').max=d;$('from').value=selection[0].toFixed(3);$('to').value=selection[1].toFixed(3);autosave();draw();if(playing)startPlayback(baselinePlaying,selection[0]);}
function range(){return [Math.max(0,Math.floor(selection[0]*HZ)),Math.min(state.rows.length,Math.ceil(selection[1]*HZ))];}
function loadSound(p){halt();base={preset:p.id,rows:clone(p.rows),pitch:p.rows.map(()=>100)};state=clone(base);track=p.track||'pitch';$('loop').checked=p.loop??true;history=[];future=[];baselineBuffer=null;selection=[0,duration()];$('preset').value=p.id;hover=0;soundInfo();syncSelection();fields();change();}
function restoreProject(p){validateProject(p);halt();state=clone(p.current);base=clone(p.baseline);history=[];future=[];baselineBuffer=null;selection=p.selection?.length===2&&p.selection.every(Number.isFinite)?p.selection:[0,duration()];track=tracks.some(t=>t.id===p.track)?p.track:'pitch';if(![...$('preset').options].some(o=>o.value===state.preset)){const o=document.createElement('option');o.value=state.preset;o.textContent='Imported sound';$('preset').append(o);} $('preset').value=state.preset;soundInfo();syncSelection();fields();change();}
const canvas=$('plot'),g=canvas.getContext('2d');let size={w:800,h:320};
const area=()=>({x:64,y:18,w:size.w-84,h:size.h-56});
function norm(v,t=def()){v=Math.max(t.min,Math.min(t.max,v));return t.log?Math.log(v/t.min)/Math.log(t.max/t.min):(v-t.min)/(t.max-t.min);}
function value(n,t=def()){return t.log?t.min*Math.pow(t.max/t.min,n):t.min+(t.max-t.min)*n;}
function point(event){const box=canvas.getBoundingClientRect(),a=area();return {i:Math.max(0,Math.min(state.rows.length-1,Math.round((event.clientX-box.left-a.x)/a.w*(state.rows.length-1)))),v:value(Math.max(0,Math.min(1,1-(event.clientY-box.top-a.y)/a.h))),t:Math.max(0,Math.min(duration(),(event.clientX-box.left-a.x)/a.w*duration()))};}
function line(a,b){const t=def(),lo=Math.min(a.i,b.i),hi=Math.max(a.i,b.i);for(let i=lo;i<=hi;i++){const f=hi===lo?0:(i-a.i)/(b.i-a.i);t.set(state,i,value(norm(a.v)+(norm(b.v)-norm(a.v))*f));}}
function draw(){if(!state)return;const a=area(),t=def(),n=state.rows.length;g.clearRect(0,0,size.w,size.h);g.font='11px system-ui';g.textAlign='right';
 for(let k=0;k<=4;k++){const y=a.y+a.h*k/4;g.strokeStyle='#28384c';g.beginPath();g.moveTo(a.x,y);g.lineTo(a.x+a.w,y);g.stroke();const v=value(1-k/4);g.fillStyle='#91a4bc';g.fillText((Math.abs(v)<100?Math.round(v*10)/10:Math.round(v))+(t.unit||''),a.x-9,y+4);}
 g.textAlign='center';for(let k=0;k<=6;k++){const x=a.x+a.w*k/6;g.fillStyle='#91a4bc';g.fillText((duration()*k/6).toFixed(2)+'s',x,a.y+a.h+23);}
 const sx=a.x+selection[0]/duration()*a.w,ex=a.x+selection[1]/duration()*a.w;g.fillStyle='#73e4cc0b';g.fillRect(sx,a.y,ex-sx,a.h);g.strokeStyle='#6bbeb199';g.strokeRect(sx,a.y,ex-sx,a.h);
 function curve(s,color,dash){g.strokeStyle=color;g.lineWidth=2;g.setLineDash(dash);g.beginPath();for(let i=0;i<n;i++){const x=a.x+i/Math.max(1,n-1)*a.w,y=a.y+(1-norm(t.get(s,i)))*a.h;i?g.lineTo(x,y):g.moveTo(x,y);}g.stroke();g.setLineDash([]);}
 curve(base,'#657b95',[4,4]);curve(state,'#7debd0',[]);
 if(playing){const x=a.x+playhead()/duration()*a.w;g.strokeStyle='#ffc978';g.beginPath();g.moveTo(x,a.y);g.lineTo(x,a.y+a.h);g.stroke();}
 const i=Math.min(hover,n-1);$('registers').textContent=compile(state.rows.slice(i,i+1),state.pitch.slice(i,i+1))[0].map((v,k)=>`R${k}:${v}`).join(' ');
}
new ResizeObserver(()=>{const r=canvas.getBoundingClientRect(),d=window.devicePixelRatio||1;size={w:r.width,h:r.height};canvas.width=Math.round(r.width*d);canvas.height=Math.round(r.height*d);g.setTransform(d,0,0,d,0,0);draw();}).observe(canvas);
canvas.onpointerdown=e=>{if(!state)return;canvas.setPointerCapture(e.pointerId);const p=point(e);pointer={start:p,last:p,mode:$('gesture').value};if(pointer.mode==='select'){selection=[p.t,p.t];draw();}else{snapshot();liveCurve=clone(state);line(p,p);change();}e.preventDefault();};
canvas.onpointermove=e=>{if(!state)return;const p=point(e);hover=p.i;$('readout').textContent=`${(p.i/HZ).toFixed(2)}s · ${Math.round(p.v*10)/10}${def().unit||''}`;if(pointer){if(pointer.mode==='select'){selection=[Math.min(pointer.start.t,p.t),Math.max(pointer.start.t,p.t)];draw();}else{if(pointer.mode==='line')state=clone(liveCurve);line(pointer.mode==='line'?pointer.start:pointer.last,p);pointer.last=p;change();}}};
canvas.onpointerup=e=>{if(!pointer)return;const mode=pointer.mode;pointer=null;canvas.releasePointerCapture(e.pointerId);if(mode==='select')syncSelection();else if($('auto').checked){wantPlay=true;audio().then(()=>{if(!dirty){wantPlay=false;startPlayback();}});}fields();};
canvas.onpointercancel=()=>{pointer=null;syncSelection();};
function download(name,data,type){const u=URL.createObjectURL(new Blob([data],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
function fileName(ext){return 'ay-sound-edited.'+ext;}
$('play').onclick=()=>startPlayback();$('stop').onclick=halt;$('baseline').onclick=()=>startPlayback(true);
$('playOnce').onclick=()=>{$('loop').checked=false;startPlayback();};
$('gain').oninput=()=>{if(gainNode)gainNode.gain.setTargetAtTime(+$('gain').value,ctx.currentTime,.01);};
$('loop').onchange=()=>{if(playing)startPlayback(baselinePlaying,playhead());};
$('curve').onchange=()=>{track=$('curve').value;fields();draw();autosave();};
$('preset').onchange=()=>{const p=presets.find(p=>p.id===$('preset').value);if(p)loadSound(p);else if(base.preset===$('preset').value){snapshot();state=clone(base);change();fields();}};
$('undo').onclick=()=>{if(!history.length)return;future.push(clone(state));state=history.pop();change();fields();};
$('redo').onclick=()=>{if(!future.length)return;history.push(clone(state));state=future.pop();change();fields();};
$('reset').onclick=()=>{snapshot();state=clone(base);change();fields();};
$('all').onclick=()=>{selection=[0,duration()];syncSelection();};
for(const id of ['from','to'])$(id).onchange=()=>{const a=+$('from').value,b=+$('to').value;if(Number.isFinite(a)&&Number.isFinite(b)){selection=[Math.min(a,b),Math.max(a,b)];syncSelection();}};
function edited(){change();if($('auto').checked){wantPlay=true;audio();}}
$('set').onclick=()=>{const v=+$('value').value,t=def();if(!Number.isFinite(v)||v<t.min||v>t.max){message(`Value must be ${t.min}–${t.max}.`);return;}snapshot();const [lo,hi]=range();for(let i=lo;i<hi;i++)t.set(state,i,v);edited();};
$('smooth').onclick=()=>{snapshot();const [lo,hi]=range(),t=def(),old=clone(state);for(let i=lo;i<hi;i++){let total=0,count=0;for(let j=Math.max(lo,i-2);j<Math.min(hi,i+3);j++){total+=norm(t.get(old,j));count++;}t.set(state,i,value(total/count));}edited();};
$('restore').onclick=()=>{snapshot();const [lo,hi]=range(),t=def();for(let i=lo;i<hi;i++)t.set(state,i,t.get(base,i));edited();};
$('save').onclick=()=>download(fileName('json'),JSON.stringify(project(),null,2),'application/json');
$('load').onclick=()=>$('file').click();$('file').onchange=async()=>{try{const f=$('file').files[0];if(!f)return;if(f.size>3000000)throw Error('Project file is too large.');restoreProject(JSON.parse(await f.text()));message('Project loaded.');}catch(e){message(e.message);}finally{$('file').value='';}};
$('import').onclick=()=>$('registerFile').click();
$('registerFile').onchange=async()=>{try{
 const f=$('registerFile').files[0];if(!f)return;if(f.size>3000000)throw Error('Register file is too large.');
 const rows=importRegisters(f.name.toLowerCase().endsWith('.json')?JSON.parse(await f.text()):new Uint8Array(await f.arrayBuffer()));
 const current={preset:'imported',rows,pitch:rows.map(()=>100)};
 restoreProject({version:1,current,baseline:clone(current),selection:[0,rows.length/HZ],track:'pitch'});
}catch(e){message(e.message);}finally{$('registerFile').value='';}};
$('exportWav').onclick=()=>{if(!samples||dirty)return;download(fileName('wav'),wav(samples),'audio/wav');};
$('exportAy').onclick=()=>download(fileName('registers.bin'),new Uint8Array(compile(state.rows,state.pitch).flat()),'application/octet-stream');
document.onkeydown=e=>{if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();playing?halt():startPlayback();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();$(e.shiftKey?'redo':'undo').click();}};
function animate(){if(playing)draw();requestAnimationFrame(animate);}animate();
try{
 const response=await fetch('./presets.json');if(!response.ok)throw Error('Cannot load starting sounds.');presets=await response.json();presets.forEach(p=>validateRows(p.rows));
 for(const t of tracks){const o=document.createElement('option');o.value=t.id;o.textContent=t.label;$('curve').append(o);}
 for(const p of presets){const o=document.createElement('option');o.value=p.id;o.textContent=p.label;$('preset').append(o);}
 for(const group of ['Sound','Levels','Individual pitch','Routing']){const h=document.createElement('h3');h.textContent=group;$('tracks').append(h);for(const t of tracks.filter(t=>t.group===group))makeButton(t,$('tracks'));}
 for(const t of tracks.filter(t=>t.advanced))makeButton(t,$('advanced'));
 let saved;try{saved=JSON.parse(localStorage.getItem(storageKey(requestedPreset)));if(saved)validateProject(saved);}catch{saved=null;}
 if(saved&&(!requestedPreset||saved.current.preset===requestedPreset))restoreProject(saved);else loadSound(presets.find(p=>p.id===requestedPreset)||presets[0]);
}catch(e){message(e.message);}
function makeButton(t,parent){const b=document.createElement('button');b.textContent=t.label;b.dataset.track=t.id;b.onclick=()=>{track=t.id;fields();draw();autosave();};parent.append(b);}

