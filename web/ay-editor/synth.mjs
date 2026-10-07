import {createAy,ayRunTo,ayTakeSample,ayWriteReg} from './ay-core.mjs';
export const CPU=3528000, FRAME=58688, HZ=CPU/FRAME, RATE=44100;
export function validateRows(rows){
 if(!Array.isArray(rows)||!rows.length||rows.length>3600)throw Error('Expected 1–3600 AY frames.');
 for(const r of rows){
  if(!Array.isArray(r)||r.length!==14||r.some(v=>!Number.isInteger(v)||v<0||v>255))throw Error('Each frame needs fourteen register bytes.');
  if([1,3,5].some(k=>r[k]>15)||r[6]>31||r[7]>63||[8,9,10].some(k=>r[k]>16)||(r[13]>15&&r[13]!==255))throw Error('A register is outside its AY range.');
 }
 return rows;
}
export function compile(rows,pitch){
 validateRows(rows);
 if(!Array.isArray(pitch)||pitch.length!==rows.length||pitch.some(v=>!Number.isFinite(v)||v<50||v>150))throw Error('Pitch curve must be 50–150% for every frame.');
 return rows.map((r,i)=>{r=[...r];if(pitch[i]===100)return r;for(let c=0;c<3;c++){const p=Math.max(1,Math.min(4095,Math.round(Math.max(1,r[c*2]+256*r[c*2+1])*100/pitch[i])));r[c*2]=p&255;r[c*2+1]=p>>8;}return r;});
}
export function render(rows){
 validateRows(rows);
 const n=Math.ceil(rows.length*FRAME*RATE/CPU),out=new Float32Array(n);
 const ay=createAy(16,CPU*680000*20e-12),a=new Float32Array(1),b=new Float32Array(1),c=new Float32Array(1);
 let frame=0,previousT=0,previousX=0,previousY=0;
 const hp=Math.exp(-2*Math.PI*20/RATE);
 for(let i=0;i<n;i++){
  const end=Math.round((i+1)*CPU/RATE);
  while(frame<rows.length&&frame*FRAME<end){
   ayRunTo(ay,frame*FRAME);
   rows[frame].forEach((v,k)=>{if(k!==13||v!==255)ayWriteReg(ay,k,v);});frame++;
  }
  ayRunTo(ay,end);ayTakeSample(ay,end-previousT,a,b,c,0);previousT=end;
  const x=(a[0]+b[0]+c[0])/3,y=x-previousX+hp*previousY;
  out[i]=y;previousX=x;previousY=y;
 }
 return out;
}
export function wav(samples){
 const data=new ArrayBuffer(44+2*samples.length),v=new DataView(data);
 const str=(at,s)=>[...s].forEach((c,i)=>v.setUint8(at+i,c.charCodeAt(0)));
 str(0,'RIFF');v.setUint32(4,data.byteLength-8,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,RATE,true);v.setUint32(28,RATE*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,samples.length*2,true);
 samples.forEach((s,i)=>v.setInt16(44+2*i,Math.round(Math.max(-1,Math.min(1,s))*32767),true));return data;
}
