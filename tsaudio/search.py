import struct, subprocess
import numpy as np
AY_CLOCK=1764750
HZ=60.1145
OBJECTIVE="joint"
LOW=80
HIGH=7000

class Simulator:
    def __init__(self,exe,env,cutoff,ratio):
        self.p=subprocess.Popen([str(exe),str(AY_CLOCK),str(cutoff),str(ratio)],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,env=env)
    def command(self,op,n=0,count=0):
        self.p.stdin.write(struct.pack('<iii',op,n,count));self.p.stdin.flush()
    def evaluate(self,rows,n):
        self.p.stdin.write(struct.pack('<iii',0,n,len(rows)))
        self.p.stdin.write(np.asarray(rows,dtype='<i4').tobytes());self.p.stdin.flush()
        needed=len(rows)*n*4; chunks=[]
        while needed:
            data=self.p.stdout.read(needed)
            if not data:raise RuntimeError('AY worker terminated')
            chunks.append(data);needed-=len(data)
        return np.frombuffer(b''.join(chunks),dtype='<f4').reshape(len(rows),n).astype(float)
    def close(self):
        self.command(3);self.p.stdin.close();self.p.stdout.close()
        assert self.p.wait(timeout=5)==0

def candidates(seed,previous,f0):
    result=[seed.copy(),previous.copy()]
    for ch in range(3):
        period=seed[ch*2]|(seed[ch*2+1]<<8)
        for factor in [.94,.98,1.02,1.06]:
            r=seed.copy();p=int(np.clip(round(period*factor),1,4095));r[ch*2:ch*2+2]=[p&255,p>>8];result.append(r)
        for p in np.unique(np.rint(np.geomspace(1,4095,18)).astype(int)):
            r=seed.copy();r[ch*2:ch*2+2]=[int(p)&255,int(p)>>8];result.append(r)
        for volume in range(17):
            r=seed.copy();r[8+ch]=volume;result.append(r)
        for xor in [1<<ch,1<<(ch+3),(1<<ch)|(1<<(ch+3))]:
            r=seed.copy();r[7]^=xor;result.append(r)
        # Audio-rate envelope trials: both tone-gated and pure envelope output.
        for shape in range(16):
            divisor=512 if shape in [10,14] else 256
            ep=int(np.clip(round(AY_CLOCK/(divisor*max(70,f0))),1,65535))
            r=seed.copy();r[11:14]=[ep&255,ep>>8,shape];r[8+ch]=16
            result.append(r.copy());r[7]|=(1<<ch)|(1<<(ch+3));result.append(r)
    for noise in range(1,32):
        r=seed.copy();r[6]=noise;result.append(r)
    # Keep shape unchanged as a distinct option: restarting can be harmful.
    if any(v==16 for v in seed[8:11]):
        r=seed.copy();r[13]=255;result.append(r)
        ep=seed[11]|(seed[12]<<8)
        for p in sorted(set([max(1,min(65535,ep+d)) for d in [-2,-1,1,2]]+
                            np.rint(np.geomspace(1,65535,20)).astype(int).tolist())):
            r=seed.copy();r[11:13]=[p&255,p>>8];r[13]=255;result.append(r)
    return [list(row) for row in dict.fromkeys(tuple(r) for r in result)]

def feature(y):
    # No sample-phase matching: compare smoothed spectra and AC energy instead.
    y=y-y.mean(axis=-1,keepdims=True)
    spectrum=abs(np.fft.rfft(y*np.hanning(y.shape[-1]),4096,axis=-1))
    frequencies=np.fft.rfftfreq(4096,1/44100)
    edges=np.geomspace(LOW,HIGH,49)
    band_values=[]
    for lo,hi in zip(edges,edges[1:]):
        bins=np.flatnonzero((frequencies>=lo)&(frequencies<hi))
        if not len(bins):bins=np.array([np.argmin(abs(frequencies-np.sqrt(lo*hi)))])
        band_values.append(np.sqrt(np.mean(spectrum[...,bins]**2,axis=-1)+1e-12))
    bands=np.stack(band_values,axis=-1)
    return bands,np.sqrt(np.mean(y*y,axis=-1)+1e-12)

def score_components(context,waves,target):
    y=np.concatenate([np.tile(context,(len(waves),1)),waves],axis=1)
    bands,rms=feature(y);tb,tr=feature(target[None,:])
    # Magnitude compression keeps weak speech bands relevant without unlimited boost.
    # A fixed floor prevents nearly silent frames dominating the entire phrase.
    error=np.mean((np.sqrt(bands)-np.sqrt(tb))**2,axis=1)/(np.mean(tb)+.2)
    error+=.25*((rms-tr)/(tr+.015))**2
    y=y-y.mean(axis=1,keepdims=True)
    t=target-target.mean()
    # Phase-aligned waveform correlation: a single bounded lag per window,
    # not time warping. Absolute AY phase is not guaranteed at cartridge start.
    window=np.hanning(len(t));yw=y*window;tw=t*window
    yf=np.fft.rfft(yw,4096,axis=1);tf=np.fft.rfft(tw,4096)
    corr=np.fft.irfft(yf*np.conj(tf),4096,axis=1)
    maxlag=220  # +/-4.99ms, less than half the ~95Hz speech period.
    peak=np.max(np.concatenate([corr[:,:maxlag+1],corr[:,-maxlag:]],axis=1),axis=1)
    norm=np.sqrt(np.sum(yw*yw,axis=1)*sum(tw*tw))
    waveform=1-np.clip(peak/(norm+1e-12),-1,1)
    # Do not penalize arbitrary phase in actual silence; RMS already checks it.
    if tr[0]<.005:waveform=np.zeros(len(waves))
    ya=np.fft.irfft(yf*np.conj(yf),4096,axis=1)
    ta=np.fft.irfft(tf*np.conj(tf),4096)
    periodicity=np.mean((ya[:,16:641]/(ya[:,:1]+1e-12)-ta[16:641]/(ta[0]+1e-12))**2,axis=1)
    slope=np.sqrt(np.mean(np.diff(y,axis=1)**2,axis=1))
    tslope=np.sqrt(np.mean(np.diff(t)**2))
    roughness=((slope-tslope)/(tslope+.015))**2
    return {'spectrum':error,'waveform':waveform,'periodicity':periodicity,'roughness':roughness}

def scores(context,waves,target):
    c=score_components(context,waves,target)
    if OBJECTIVE=='spectrum':return c['spectrum']
    return c['spectrum']+.8*c['waveform']+.5*c['periodicity']+.1*c['roughness']

def render(sim,rows):
    sim.command(2); audio=[]
    for i,r in enumerate(rows):
        n=round((i+1)*44100/HZ)-round(i*44100/HZ)
        audio.append(sim.evaluate([r],n)[0]);sim.command(1,0)
    return np.concatenate(audio)
