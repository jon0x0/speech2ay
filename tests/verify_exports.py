"""Build every format/codec from a generated, redistributable audio fixture."""
import argparse,json,math,struct,subprocess,sys,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.build import build
from tsaudio.codecs import CODECS,encode

def main():
    p=argparse.ArgumentParser();p.add_argument('--pasmo',required=True);p.add_argument('--out',type=Path,default=Path('build/exports'));a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);wav=out/'synthetic.wav'
    with wave.open(str(wav),'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'))
        w.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*190*i/16000)+3000*math.sin(2*math.pi*570*i/16000))) for i in range(4000)))
    entries=[]
    for codec in CODECS:
        raw,n,meta=encode(wav,codec);entries.append({'name':'SYNTHETIC','codec':codec,'data':raw,'count':n,**meta})
    for fmt in ['bin','tap','dck']:
        build(entries,out/fmt,[fmt],0x8000,a.pasmo)
    dck=(out/'dck/demo.dck').read_bytes();rom=(out/'dck/picorom.bin').read_bytes()
    assert dck[:9]==bytes([0,0,0,0,0,2,2,0,0])
    assert len(rom)==65536 and rom[32768:49152]==dck[9:] and set(rom[49152:])=={255}
    tap=(out/'tap/demo.tap').read_bytes();pos=0;blocks=[]
    while pos<len(tap):
        n=int.from_bytes(tap[pos:pos+2],'little');data=tap[pos+2:pos+2+n];pos+=n+2
        xor=0
        for v in data:xor^=v
        assert xor==0;blocks.append(data)
    assert pos==len(tap) and len(blocks)==4 and blocks[3][1:-1]==(out/'tap/player.bin').read_bytes()
    build(entries,out/'separate',['bin'],0x9000,a.pasmo,True,0xd000)
    print('All six codecs, TAP checksums, ROM-only DCK/PicoROM mapping, and relocated separate-data export passed')
if __name__=='__main__':main()
