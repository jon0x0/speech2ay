// Audio Lab integration around TSRun's live public modules.
// Upstream: https://github.com/josef-jelinek/TSRun
const upstream='https://josef-jelinek.github.io/TSRun/';
const frameMs=1000*58688/3528000;
function notify(type,message){window.parent.postMessage({type,message},location.origin);}
async function resource(path,binary=false){
  const response=await fetch(path);
  if(!response.ok)throw new Error(`Could not load ${path}: HTTP ${response.status}`);
  return binary?new Uint8Array(await response.arrayBuffer()):response.text();
}
async function boot(){
  const [cpu,video,sound,keys,pads]=await Promise.all(
    ['machine.js','screen.js','sound.js','keyboard.js','joystick.js'].map(path=>import(upstream+path)));
  const canvas=document.getElementById('screen');
  const matrix=new Uint8Array(8),joystick=new Uint8Array(2);
  const kbd=keys.initKeyboard(document.getElementById('keyboard'),matrix);
  pads.initJoysticks(joystick);
  const machine=cpu.createMachine(matrix,joystick);
  const [rom0,rom1,cartridge,vert,frag]=await Promise.all([
    resource(upstream+'roms/ts2068-0.rom',true),resource(upstream+'roms/ts2068-1.rom',true),
    resource('../assets/TS2068-Audio-Lab.dck',true),
    resource(upstream+'screen.vert.glsl'),resource(upstream+'screen.frag.glsl')]);
  if(rom0.length!==16384||rom1.length!==8192)throw new Error('Unexpected TS2068 system ROM sizes.');
  machine.homeRom.set(rom0);machine.exRom.set(rom1);
  const cartError=cpu.insertDock(machine,cartridge);
  if(cartError)throw new Error(cartError);
  cpu.resetMachine(machine);
  let gfx=null;
  await new Promise((resolve,reject)=>video.initScreen(canvas,{vert,frag},(err,value)=>{
    if(err||!value){reject(new Error(err||'WebGL2 unavailable'));notify('audio-lab-error',err);return;}
    gfx=value;video.setCrt(gfx,false);resolve();
  }));
  const sfx=await new Promise((resolve,reject)=>sound.initSound(44100,(err,value)=>{
    if(err||!value)reject(new Error(err||'Web Audio unavailable'));else resolve(value);
  }));
  cpu.setSoundRate(machine,sfx.context.sampleRate);cpu.enableSound(machine,true);sound.setSoundStereo(sfx,false);
  let last=0,carry=frameMs,started=false;
  function step(){
    cpu.runFrame(machine);
    const chunk=cpu.takeAudio(machine);
    if(chunk.n>0&&(sound.soundIsRunning(sfx)||!sound.soundQueueReady(sfx)))sound.pushSound(sfx,chunk);
  }
  function frame(now){
    requestAnimationFrame(frame);
    pads.pollJoysticks(joystick);
    if(!last)last=now;
    carry+=Math.min(80,now-last);last=now;
    let ran=0;
    while(carry>=frameMs&&ran<4){step();carry-=frameMs;ran++;}
    if(started&&sound.soundIsRunning(sfx)&&!sound.soundQueueReady(sfx)&&ran<4){step();carry=Math.max(carry,0)-frameMs;}
    video.drawScreen(gfx,machine.pixels);
  }
  window.audioLab={
    start(){started=true;sound.resumeSound(sfx);window.focus();canvas.focus();return true;},
    press(code){
      this.start();const event={code,preventDefault(){},repeat:false};
      keys.handleKeyDown(kbd,event);setTimeout(()=>keys.handleKeyUp(kbd,event),120);
    },
    reset(){keys.handleBlur(kbd);sound.resetSound(sfx);cpu.resetMachine(machine);},
  };
  window.addEventListener('keydown',event=>{window.audioLab.start();keys.handleKeyDown(kbd,event);});
  window.addEventListener('keyup',event=>keys.handleKeyUp(kbd,event));
  window.addEventListener('blur',()=>keys.handleBlur(kbd));
  window.addEventListener('pointerdown',()=>window.audioLab.start());
  window.addEventListener('resize',()=>video.resizeScreen(gfx));
  requestAnimationFrame(frame);
  notify('audio-lab-ready');
}
boot().catch(error=>{
  console.error(error);
  const message='TSRun could not start. '+error.message;
  document.getElementById('error').hidden=false;document.getElementById('error').textContent=message;
  notify('audio-lab-error',message);
});
