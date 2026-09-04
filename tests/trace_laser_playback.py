"""Trace real AY port writes for every Laser AY choice in both display modes."""
import argparse
import json
from pathlib import Path
import re
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'examples')]
from update_comparison import read_entries
from tsaudio.build import assemble
from run_fuse_debug import run_fuse

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--pasmo',required=True)
    p.add_argument('--fuse',required=True,type=Path)
    a=p.parse_args();folder=a.directory.resolve()
    manifest=json.loads((folder/'manifest.json').read_text())
    entries=read_entries(folder)
    sample=manifest['sample_names'].index('Laser')
    first=next(i for i,c in enumerate(manifest['codecs']) if c.startswith('harmonic'))
    selected=[e for e in entries if e['name']=='Laser' and e['codec'] in manifest['codecs'][first:]]
    modes=2 if manifest.get('spectra') else 1
    harness=f'''
test_start:
 di
 ld a,{sample}
 ld (ui),a
 xor a
 ld (ui+17),a
 ld a,{first}
 ld (ui+1),a
test_play:
 call redraw
 jp play
test_next:
 di
 ld a,(ui+1)
 inc a
 cp CODEC_COUNT
 jr z,test_mode
 ld (ui+1),a
 jp test_play
test_mode:
 ld a,{first}
 ld (ui+1),a
 ld a,(ui+17)
 inc a
 cp {modes}
 jp z,test_finished
 ld (ui+17),a
 jp test_play
test_finished: jp test_finished
'''
    source=(folder/'player.asm').read_text()
    source=source.replace('menu:\n','menu:\n jp test_start\n',1)
    source=source.replace('\ndone:\n','\ndone:\n jp test_next\n',1)+harness
    out=folder/'laser-port-trace';out.mkdir(exist_ok=True)
    (out/'wave-tiles.bin').write_bytes((folder/'wave-tiles.bin').read_bytes())
    raw,symbols=assemble(source,out,a.pasmo);assert len(raw)<=8192
    rom=bytearray((folder/'picorom.bin').read_bytes())
    rom[32768:40960]=raw.ljust(8192,b'\xff')
    (out/'test.dck').write_bytes(bytes([0]+[2]*8)+rom)
    commands=f'''breakpoint port write 0xfff6 if z80:pc >= 0x8008 && z80:pc < 0xa000
commands 1
print spectrum:frames
print ula:tstates
print ay:current
print z80:af
continue
end
breakpoint {symbols['test_finished']}
commands 2
exit 0
end'''
    result=run_fuse(machine='ts2068',media=out/'test.dck',fuse=a.fuse,debugger_command=commands,timeout=55)
    (out/'trace.log').write_text(result.stdout+result.stderr)
    numbers=[int(x,16) for x in re.findall(r'^0x([0-9a-f]+)$',result.stdout,re.M|re.I)]
    assert len(numbers)%4==0
    actual=[(numbers[i],numbers[i+1],numbers[i+2],numbers[i+3]>>8) for i in range(0,len(numbers),4)]
    init=[(7,63),(8,0),(9,0),(10,0)]
    expected=list(init);ranges=[]
    for mode in range(modes):
        for entry in selected:
            expected+=init;start=len(expected)
            data=entry['data']
            for offset in range(0,len(data),14):
                row=data[offset:offset+14]
                expected+=list(enumerate(row[:13]))+([(13,row[13])] if row[13]!=255 else [])
            end=len(expected);expected += [(8,0),(9,0),(10,0)]
            ranges.append((mode,entry['codec'],start,end,entry['count']))
    observed=[(reg,value) for _,_,reg,value in actual]
    mismatch=next(((i,x,y) for i,(x,y) in enumerate(zip(observed,expected)) if x!=y),None)
    assert observed==expected,(len(observed),len(expected),mismatch)
    clips=[]
    for mode,codec,start,end,count in ranges:
        starts=[frame for frame,_,reg,_ in actual[start:end] if reg==0]
        assert len(starts)==count
        assert all(y-x==1 for x,y in zip(starts,starts[1:])),(mode,codec,starts)
        assert actual[end][0]==starts[-1]+1,(mode,codec,'final frame truncated')
        clips.append({'mode':mode,'codec':codec,'frames':count,'cadence_frames':1})
    report={'exact_port_writes':len(actual),'clips':clips,'matches_cartridge_data':True}
    (out/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))

if __name__=='__main__':main()
