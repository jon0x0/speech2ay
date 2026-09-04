const frame=document.getElementById('emulator');
const start=document.getElementById('start');
const status=document.getElementById('status');
const panel=document.getElementById('start-panel');
const error=document.getElementById('error');
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
  if(event.data?.type==='audio-lab-ready'){
    start.disabled=false;start.textContent='Start Audio Lab';status.textContent='Cartridge loaded';
  }else if(event.data?.type==='audio-lab-error'){
    error.textContent=event.data.message;status.textContent='Loading failed';
  }
});
start.addEventListener('click',()=>{
  if(!frame.contentWindow.audioLab?.start()){
    error.textContent='Audio is not ready. Try again in a moment, or use a browser with Web Audio support.';return;
  }
  panel.hidden=true;status.textContent='Running · mono AY audio';
});
document.querySelectorAll('[data-key]').forEach(button=>button.addEventListener('click',()=>{
  if(!panel.hidden)return;
  frame.contentWindow.audioLab?.press(button.dataset.key);
}));
document.getElementById('reset').addEventListener('click',()=>frame.contentWindow.audioLab?.reset());
document.getElementById('fullscreen').addEventListener('click',()=>{
  const request=frame.requestFullscreen?.();request?.catch(()=>{status.textContent='Full screen unavailable in this browser';});
});
setTimeout(()=>{
  if(start.disabled){error.textContent='The emulator is taking longer than expected. Reload, or download the DCK to use in another emulator.';}
},20000);
