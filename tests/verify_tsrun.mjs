// Usage: node tests/verify_tsrun.mjs /path/to/TSRun web/assets/TS2068-Audio-Lab.dck
// Exercises the engine directly, including real emulated keyboard input.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const upstream=path.resolve(process.argv[2]);
const api=await import(pathToFileURL(path.join(upstream,'machine.js')));
const keys=new Uint8Array(8).fill(31),sticks=new Uint8Array(2).fill(255);
const m=api.createMachine(keys,sticks);
m.homeRom.set(fs.readFileSync(path.join(upstream,'roms/ts2068-0.rom')));
m.exRom.set(fs.readFileSync(path.join(upstream,'roms/ts2068-1.rom')));
assert.equal(api.insertDock(m,fs.readFileSync(process.argv[3])),null);
api.resetMachine(m);api.setSoundRate(m,44100);api.enableSound(m,true);
function run(n){
  let energy=0;
  for(let i=0;i<n;i++){
    api.runFrame(m);const c=api.takeAudio(m);
    for(let j=0;j<c.n;j++){const v=c.a[j]+c.b[j]+c.c[j];energy+=v*v;}
  }
  return energy;
}
function press(row,bit){keys[row]&=~(1<<bit);run(10);keys[row]=31;run(30);}
run(250);
assert.equal(m.ram[0xc230],0);assert.equal(m.ram[0xc231],0);
let writes=0;
const write=m.bus.ioWrite;
m.bus.ioWrite=(port,value)=>{if((port&255)===246)writes++;write(port,value);};
const reports=[];
for(let sample=0;sample<4;sample++){
  for(let codec=0;codec<10;codec++){
    assert.equal(m.ram[0xc230],sample);assert.equal(m.ram[0xc231],codec);
    const before=writes;
    keys[7]&=~1;const first=run(5);keys[7]=31;const rest=run(190);
    assert.ok(writes-before>20,`No audio writes: ${sample}/${codec}`);
    assert.ok(first+rest>0,`Silent output: ${sample}/${codec}`);
    assert.equal(m.ram[0xc215],0,'AY playback did not finish');
    assert.equal(m.ram[0xc232],0,'DAC playback did not finish');
    reports.push({sample:sample+1,codec,writes:writes-before});
    if(codec<9)press(1,0);
  }
  if(sample<3){for(let i=0;i<9;i++)press(2,0);press(5,0);}
}
press(1,1);assert.equal(m.ram[0xc241],1,'Spectrum toggle failed');
press(1,1);assert.equal(m.ram[0xc241],0,'Menu toggle failed');
console.log(JSON.stringify({passed:reports.length,entries:reports,spectraToggle:true},null,2));
