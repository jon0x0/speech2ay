import {compile,validateRows} from './synth.mjs';
export function importRegisters(data){
 let rows;
 if(data instanceof Uint8Array){
  if(!data.length||data.length%14||data.length>3600*14)throw Error('Raw input must contain 1–3600 complete 14-byte AY frames.');
  if(new TextDecoder().decode(data.slice(0,8))==='ZXAYEMUL')throw Error('ZXAYEMUL files contain Z80 programs, not raw register frames.');
  rows=Array.from({length:data.length/14},(_,i)=>Array.from(data.slice(i*14,i*14+14)));
 }else rows=Array.isArray(data)?data:data?.rows;
 validateRows(rows);return rows.map(r=>[...r]);
}
export function validateProject(p){
 if(p?.version!==1||!p.current||!p.baseline)throw Error('Not a version 1 AY editor project.');
 for(const s of [p.current,p.baseline]){
  if(typeof s.preset!=='string'||!s.preset.length||s.preset.length>200)throw Error('Project needs a sound identifier.');
  compile(s.rows,s.pitch);
 }
 if(p.current.rows.length!==p.baseline.rows.length)throw Error('Starting and edited frame counts differ.');
 return p;
}
