import fs from 'node:fs';import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {compile,render,wav,HZ,RATE,CPU,FRAME,validateRows} from './synth.mjs';
import {importRegisters,validateProject} from './formats.mjs';
const presets=JSON.parse(fs.readFileSync(new URL('./presets.json',import.meta.url)));
const provenance=JSON.parse(fs.readFileSync(new URL('./provenance.json',import.meta.url)));
assert.equal(createHash('sha256').update(fs.readFileSync(new URL('./ay-core.mjs',import.meta.url))).digest('hex'),provenance.sha256);
const gunshot=presets.find(p=>p.id==='real-gunshot-full');
assert.equal(gunshot.rows.length,30);
assert.equal(createHash('sha256').update(new Uint8Array(gunshot.rows.flat())).digest('hex'),provenance.gunshot.register_sha256);
let maxMs=0;
for(const p of presets){
 assert.deepEqual(compile(p.rows,p.rows.map(()=>100)),p.rows,'unchanged export is byte exact');
 const t=performance.now(),samples=render(p.rows);maxMs=Math.max(maxMs,performance.now()-t);
 assert.equal(samples.length,Math.ceil(p.rows.length*FRAME*RATE/CPU));assert.ok(samples.every(Number.isFinite));
 const b=new DataView(wav(samples));assert.equal(b.getUint32(24,true),44100);assert.equal(b.getUint32(40,true),samples.length*2);
}
const silent=Array.from({length:60},()=>[100,0,100,0,100,0,5,63,0,0,0,1,0,255]);
assert.ok(render(silent).every(x=>x===0));
const tone=silent.map(r=>{r=[...r];r[7]=62;r[8]=15;return r;});
function cycles(x){let n=0;for(let i=5001;i<x.length;i++)if(x[i-1]<0&&x[i]>=0)n++;return n;}
const nominal=cycles(render(tone)),raised=cycles(render(compile(tone,tone.map(()=>110))));
assert.ok(raised/nominal>1.09&&raised/nominal<1.12,'pitch changes frequency');
const quiet=tone.map(r=>{r=[...r];r[8]=8;return r;});
const energy=x=>x.reduce((s,v)=>s+v*v,0)/x.length;
assert.ok(energy(render(quiet))<energy(render(tone))*.2,'volume changes audible energy');
const noise=tone.map(r=>{r=[...r];r[7]=55;r[6]=24;return r;});assert.notDeepEqual(render(noise),render(tone));
const env=tone.map((r,i)=>{r=[...r];r[8]=16;r[11]=8;r[13]=i?255:10;return r;});
assert.notDeepEqual(render(env),render(tone));
const restart=env.map(r=>{r=[...r];r[13]=10;return r;});assert.notDeepEqual(render(env),render(restart),'R13 sentinel preserves envelope phase');
assert.throws(()=>validateRows([[1]]));assert.throws(()=>compile(tone,[100]));
const report={presets:presets.length,byteExactUneditedExport:true,pitchRatio:raised/nominal,silenceVolumeNoiseEnvelopeTests:true,maxRenderMs:maxMs};
for(const p of presets){
 assert.deepEqual(importRegisters(new Uint8Array(p.rows.flat())),p.rows);
 assert.deepEqual(importRegisters(JSON.parse(JSON.stringify({rows:p.rows}))),p.rows);
 const current={preset:p.id,rows:p.rows,pitch:p.rows.map(()=>100)};
 assert.deepEqual(validateProject(JSON.parse(JSON.stringify({version:1,current,baseline:current}))).current,current);
}
assert.equal(render([tone[0]]).length,Math.ceil(FRAME*RATE/CPU));
assert.throws(()=>importRegisters(new Uint8Array(15)));
assert.throws(()=>importRegisters({rows:[[0]]}));
assert.throws(()=>importRegisters([[...tone[0].slice(0,13),16]]));
assert.throws(()=>validateProject({version:1,current:{rows:tone,pitch:tone.map(()=>100)},baseline:{}}));
report.importAndProjectRoundtrips=true;
fs.writeFileSync(new URL('./verification.json',import.meta.url),JSON.stringify(report,null,2));console.log(report);
