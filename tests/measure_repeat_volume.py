"""Capture repeated real Fuse playback; report AC RMS per codec and repeat."""
import argparse, json, re, subprocess, sys, wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.build import assemble
from capture_fuse_audio import extract

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--sample',default='Laser')
    p.add_argument('--pasmo',required=True)
    p.add_argument('--fuse',required=True)
    p.add_argument('--gap-frames',type=int,default=0,help='Extra idle frames between repeats (0..250)')
    a=p.parse_args(); folder=a.directory.resolve()
    manifest=json.loads((folder/'manifest.json').read_text())
    sample=manifest['sample_names'].index(a.sample)
    if not 0<=a.gap_frames<=250:p.error('--gap-frames must be 0..250')
    out=folder/('repeat-'+str(sample)+(f'-gap{a.gap_frames}' if a.gap_frames else ''));out.mkdir(exist_ok=True)
    harness=f'''
repeat_start:
 di
 ld a,{sample}
 ld (ui),a
 xor a
 ld (ui+1),a
 ld (ui+17),a
 ld (repeat_index),a
repeat_play:
 call redraw
 jp play
repeat_next:
 di
 ld a,(repeat_index)
 inc a
 cp 3
 jr z,repeat_codec
 ld (repeat_index),a
 ; Different idle delays exercise free-running AY generator state.
 add a,{a.gap_frames}
 ld b,a
 ei
repeat_wait:
 halt
 djnz repeat_wait
 di
 jp repeat_play
repeat_codec:
 xor a
 ld (repeat_index),a
 ld a,(ui+1)
 inc a
 cp CODEC_COUNT
 jp z,repeat_finished
 ld (ui+1),a
 jp repeat_play
repeat_finished: jp repeat_finished
repeat_index equ $c260
'''
    source=(folder/'player.asm').read_text().replace('menu:\n','menu:\n jp repeat_start\n',1)
    source=source.replace('\ndone:\n','\ndone:\n jp repeat_next\n',1)+harness
    (out/'wave-tiles.bin').write_bytes((folder/'wave-tiles.bin').read_bytes())
    raw,s=assemble(source,out,a.pasmo);assert len(raw)<=8192
    rom=bytearray((folder/'picorom.bin').read_bytes());rom[32768:40960]=raw.ljust(8192,b'\xff')
    cart=out/'test.dck';cart.write_bytes(bytes([0]+[2]*8)+rom)
    commands=[]
    for n,label in enumerate(['play','repeat_next','repeat_finished'],1):
        commands += [f'breakpoint {s[label]}',f'commands {n}',f'print {n}',
                     'print spectrum:frames','print ula:tstates',
                     'exit 0' if n==3 else 'continue','end']
    movie=out/'capture.fmf'
    args=[a.fuse,'--machine','ts2068','--speed','100','--sound','--no-loading-sound',
          '--movie-start',str(movie),'--movie-compr','Lossless','--dock',str(cart),
          '--debugger-command','\n'.join(commands)]
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    r=subprocess.run(args,capture_output=True,text=True,timeout=180,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'trace.log').write_text(r.stdout+r.stderr);assert r.returncode==0
    extract(movie)
    values=[int(x,16) for x in re.findall(r'^0x([0-9a-f]+)$',r.stdout,re.M|re.I)]
    rows=[values[i:i+3] for i in range(0,len(values),3)]
    with wave.open(str(movie.with_suffix('.wav')),'rb') as w:
        fs=w.getframerate();audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,w.getnchannels()).mean(axis=1)
    report=[]
    for index,codec in enumerate(manifest['codecs']):
        rms=[]
        for repeat in range(3):
            start,end=rows[(index*3+repeat)*2:(index*3+repeat)*2+2]
            assert start[0]==1 and end[0]==2
            t0=(start[1]*58688+start[2])/3528000
            t1=(end[1]*58688+end[2])/3528000
            clip=audio[round((t0+.025)*fs):round((t1-.005)*fs)]
            rms.append(float(np.sqrt(np.mean((clip-clip.mean())**2))))
        report.append(dict(codec=codec,rms=rms,spread_db=float(20*np.log10(max(rms)/min(rms)))))
    (out/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
