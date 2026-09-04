"""Verify interrupt AY writes, R13 event semantics, final-frame hold and stop."""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.assembly import runtime
from tsaudio.build import assemble
from run_fuse_debug import run_fuse
def main():
    p=argparse.ArgumentParser();p.add_argument('--pasmo',required=True);p.add_argument('--fuse',required=True,type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    rows=[[20+i,0,40,0,80,0,3,56,10,9,8,30,0,10 if i==0 else 255] for i in range(5)]
    source='''org $8000
 defb 2,2,8,$80,$ef,1,0,0
 di
 ld a,$30
 out ($f4),a
 ld sp,$ff00
 ld hl,$c000
 ld de,$c001
 ld bc,256
 ld (hl),$c1
 ldir
 ld a,$c3
 ld ($c1c1),a
 ld hl,isr
 ld ($c1c2),hl
 ld a,$c0
 ld i,a
 im 2
 call audio_init
 ld hl,frames
 ld de,5
 call ay_start
 ei
waiting:
 halt
 ld a,(state+5)
 or a
 jr nz,waiting
done: jp done
isr:
 push af
 push bc
 push de
 push hl
 call ay_tick
 pop hl
 pop de
 pop bc
 pop af
 ei
 reti
state equ $c210
'''+runtime()+'frames: defb '+','.join(str(v) for r in rows for v in r)+'\n'
    raw,s=assemble(source,out,a.pasmo);(out/'test.dck').write_bytes(bytes([0,0,0,0,0,2,2,0,0])+raw.ljust(16384,b'\xff'))
    command=f'''breakpoint port write 0xfff6 if z80:pc >= 0x8008 && z80:pc < 0xc000
commands 1
print spectrum:frames
print ay:current
print z80:af
continue
end
breakpoint {s['done']}
commands 2
exit 0
end'''
    r=run_fuse(machine='ts2068',media=out/'test.dck',fuse=a.fuse,debugger_command=command,timeout=20)
    (out/'trace.log').write_text(r.stdout+r.stderr)
    v=[int(x,16) for x in re.findall(r'^0x([0-9a-f]+)$',r.stdout,re.M|re.I)];trace=[v[i:i+3] for i in range(0,len(v),3)]
    expected=[(7,63),(8,0),(9,0),(10,0)]
    for row in rows:expected+=list(enumerate(row[:13]))+([(13,row[13])] if row[13]!=255 else [])
    expected +=[(8,0),(9,0),(10,0)]
    assert [(reg,af>>8) for _,reg,af in trace]==expected
    starts=[frame for frame,reg,af in trace if reg==0]
    assert all(b-a==1 for a,b in zip(starts,starts[1:]))
    assert trace[-1][0]==starts[-1]+1,'last frame was truncated'
    report={'frames':len(rows),'writes':len(trace),'cadence_frames':1,'r13_skip_verified':True,'final_frame_full_duration':True}
    (out/'verification.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()
