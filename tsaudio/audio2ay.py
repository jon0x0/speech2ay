"""Optional adapter for upstream Audio2AY's packed period/volume records."""
import math,struct,subprocess,wave
from .dsp import read_wav

def convert(path,exe,out):
    fs,x=read_wav(path)
    if not x:raise ValueError('Empty WAV')
    step=fs//50;window=1<<(step-1).bit_length();frames=math.ceil(len(x)/step)
    padded=x+[0]*(frames*step+window-len(x))
    wav=out/'audio2ay-input.wav';dat=out/'audio2ay.dat'
    with wave.open(str(wav),'wb') as w:
        w.setparams((1,2,fs,0,'NONE','not compressed'))
        w.writeframes(struct.pack('<'+'h'*len(padded),*(max(-32768,min(32767,round(v*32767))) for v in padded)))
    command=[str(exe),str(wav),'--output='+str(dat),'--ayrate=1764750','--frames=1','--channels=3','--arplast=0']
    result=subprocess.run(command,capture_output=True,text=True,check=True)
    (out/'audio2ay.log').write_text(result.stdout+result.stderr)
    raw=dat.read_bytes();channels,hold,n=struct.unpack('<BBH',raw[:4])
    if (channels,hold)!=(3,1) or len(raw)!=4+n*6:raise ValueError('Unsupported Audio2AY data layout')
    rows=[]
    for i in range(n):
        r=[1,0,1,0,1,0,0,56,0,0,0,1,0,255]
        for c in range(3):
            v=struct.unpack_from('<H',raw,4+i*6+c*2)[0]
            r[c*2:c*2+2]=[v&255,(v>>8)&15];r[8+c]=v>>12
        rows.append(r)
    # Frame-rate conversion preserves duration; repeating at60Hz would speed up50Hz data.
    count=math.ceil(len(x)/fs*60.1145)
    rows=[rows[min(n-1,int(i*50/60.1145))] for i in range(count)]
    return bytes(v for r in rows for v in r),count,{'seconds':count/60.1145,'source_seconds':len(x)/fs,'upstream_hz':50,'command':command}
