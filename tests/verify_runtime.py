"""Real Fuse output-value/cadence verification, independent of DAC encoder."""
import argparse,json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.assembly import runtime
from tsaudio.build import assemble
from tsaudio.codecs import DELTAS
from run_fuse_debug import run_fuse

def main():
    p=argparse.ArgumentParser();p.add_argument('--animated',action='store_true');p.add_argument('--scroll',action='store_true');p.add_argument('--pasmo',required=True);p.add_argument('--fuse',type=Path,required=True);p.add_argument('--out',type=Path,default=Path('build/verify'));a=p.parse_args()
    report={}
    for name,bits,group,periods in [('dac5',4,10,[705,706,705,706,706]*2),('dac6',4,2,[588]*2),('dpcm6',3,8,[588]*8)]:
        out=(a.out/name).resolve();out.mkdir(parents=True,exist_ok=True)
        codes=[i%(1<<bits) for i in range(group*60)]
        packed=sum(v<<(bits*i) for i,v in enumerate(codes)).to_bytes(len(codes)*bits//8,'little')
        source=' org $8000\n defb 2,2,8,$80,$ef,1,0,0\n di\n ld a,$30\n out ($f4),a\n xor a\n out ($ff),a\n ld sp,$ff00\n ld a,$c0\n ld i,a\n ld hl,sample\n ld de,60\n call '+name+'\ndone: jp done\nstate equ $c210\n'+runtime(animated='scroll' if a.scroll else a.animated)+'sample: defb '+','.join(map(str,packed))+'\n'
        if a.animated or a.scroll:
            source=source.replace(' ld hl,sample', ' ld hl,$c000\n ld de,$c001\n ld bc,256\n ld (hl),$c1\n ldir\n ld a,$fb\n ld ($c1c1),a\n ld a,$ed\n ld ($c1c2),a\n ld a,$4d\n ld ($c1c3),a\n im 2\n ld hl,sample',1)
        if a.scroll:
            source=source.replace('ld a,$30','ld a,$10').replace('state equ $c210','state equ $c210\nwave_src equ $c220').replace(' ld hl,sample', ' ld hl,$a000\n ld (wave_src),hl\n ld hl,sample',1)
        raw,sym=assemble(source,out,a.pasmo)
        (out/'test.dck').write_bytes(bytes([0,0,0,0,0,2,2,0,0])+raw.ljust(16384,b'\xff'))
        commands=''
        for i in range(group):
            commands+=f'breakpoint {sym[name+"_out"+str(i)]}\ncommands {i+1}\nprint spectrum:frames\nprint ula:tstates\nprint z80:af\ncontinue\nend\n'
        commands+=f'breakpoint {sym["done"]}\ncommands {group+1}\nexit 0\nend\n'
        run=run_fuse(machine='ts2068',media=out/'test.dck',debugger_command=commands,fuse=a.fuse,timeout=25)
        (out/'trace.log').write_text(run.stdout+run.stderr)
        vals=[int(v,16) for v in re.findall(r'^0x([0-9a-f]+)$',run.stdout,re.M|re.I)]
        rows=[vals[i:i+3] for i in range(0,len(vals),3)]
        assert len(rows)==len(codes),(name,len(rows))
        expected=codes
        if bits==3:
            previous=11;expected=[]
            for c in codes:previous=min(15,max(0,previous+DELTAS[c]));expected.append(previous)
        assert [r[2]>>8 for r in rows]==expected,(name,'wrong output')
        times=[r[0]*58688+r[1] for r in rows]
        gaps=[b-a for a,b in zip(times,times[1:])]
        assert gaps==[periods[i%group] for i in range(len(gaps))],(name,gaps)
        report[name]={'samples':len(rows),'periods_tstates':sorted(set(gaps)),'values_match':True}
    (a.out/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()
