"""Stateful Ayumi search; retain baseline unless full-clip gates pass."""
import os, shutil, subprocess
from pathlib import Path
import numpy as np
from . import search
from .codecs import encode, source
from .dsp import resample, read_wav

def accepts(current,trial,objective,mode):
    def total(m):
        return m['spectrum']+(0 if objective=='spectrum' else .8*m['waveform']+.5*m['periodicity']+.1*m['roughness'])
    guards=tuple(current) if mode=='conservative' else ('spectrum','waveform') if objective=='joint' else ()
    return total(trial)<total(current) and all(trial[k]<=current[k]+1e-10 for k in guards)

def optimize(path,channels,args,out):
    profile=getattr(args,'profile','filtered')
    mode=getattr(args,'search_mode','auto')
    if mode=='auto':mode='free' if profile=='berzerk' else 'conservative'
    raw,count,info=encode(path,f'harmonic{channels}',args.low,args.high,profile)
    baseline=[list(raw[i:i+14]) for i in range(0,len(raw),14)]
    search.LOW=args.low;search.HIGH=args.high
    # The game's effect builder used spectrum candidate search, followed by
    # full-clip joint acceptance gates. Keep those two decisions distinct.
    search.OBJECTIVE='spectrum' if profile=='berzerk' else args.objective
    gcc=shutil.which(args.gcc)
    if not gcc:raise ValueError('GCC required for ayfit; supply --gcc')
    ayumi=Path(args.ayumi).resolve()
    if not (ayumi/'ayumi.c').exists():raise ValueError('--ayumi must name the directory containing ayumi.c and ayumi.h')
    exe=out/('ay-worker.exe' if os.name=='nt' else 'ay-worker')
    subprocess.run([gcc,'-O2','-std=c99','-I'+str(ayumi),str(Path(__file__).with_name('ay_optimizer_worker.c')),str(ayumi/'ayumi.c'),'-lm','-o',str(exe)],check=True)
    env=dict(os.environ);env['PATH']=str(Path(gcc).parent)+os.pathsep+env.get('PATH','')
    sim=search.Simulator(exe,env,args.feedback_cutoff,args.feedback_gain)
    evaluations=0
    try:
        reference=search.render(sim,baseline)
        if profile=='berzerk':
            fs,x=read_wav(path);x=np.asarray(x)
            target=np.asarray([x[min(int(i*fs/44100),len(x)-1)]*(1-i*fs/44100%1)+x[min(int(i*fs/44100)+1,len(x)-1)]*(i*fs/44100%1) for i in range(round(len(x)*44100/fs))])
        else:
            fs,x=source(path,args.low,args.high)
            target=np.asarray(resample(x,fs,44100))
        target=np.pad(target,(0,max(0,len(reference)-len(target))))[:len(reference)]
        target*=np.std(reference)/(np.std(target)+1e-12)
        sim.command(2);context=np.zeros(1024)
        previous=[1,0,1,0,1,0,5,63,0,0,0,1,0,255] if profile=='berzerk' else baseline[0]
        proposal=[]
        for i,seed in enumerate(baseline):
            lo,hi=round(i*44100/search.HZ),round((i+1)*44100/search.HZ)
            expected=np.r_[np.pad(target[max(0,lo-1024):lo],(max(0,1024-lo),0)),target[lo:hi]]
            best=seed.copy()
            if any(seed[8:11]):
                for _ in range(args.passes):
                    choices=search.candidates(best,previous,info['analysis'][i]['f0_hz'] or 96,
                                              anchor=seed if mode=='conservative' else None)
                    for r in choices:
                        for c in range(channels,3):r[8+c]=0;r[7]|=(1<<c)|(1<<(c+3))
                    waves=sim.evaluate(choices,hi-lo);evaluations+=len(choices)
                    best=choices[int(np.argmin(search.scores(context,waves,expected)))]
            wave=sim.evaluate([best],hi-lo)[0];sim.command(1,0)
            context=np.r_[context,wave][-1024:];proposal.append(best);previous=best.copy();previous[13]=255
        def metrics(audio):
            rows=[]
            for i in range(count):
                lo,hi=round(i*44100/search.HZ),round((i+1)*44100/search.HZ)
                context=np.pad(audio[max(0,lo-1024):lo],(max(0,1024-lo),0))
                expected=np.r_[np.pad(target[max(0,lo-1024):lo],(max(0,1024-lo),0)),target[lo:hi]]
                rows.append(search.score_components(context,audio[None,lo:hi],expected))
            return {k:float(np.mean([r[k][0] for r in rows])) for k in rows[0]}
        old=metrics(reference);current=old;retained=baseline;accepted=0
        for size in [count,4,1]:
            for lo in range(0,count,size):
                hi=min(count,lo+size);trial=[r.copy() for r in retained];trial[lo:hi]=proposal[lo:hi]
                if trial==retained:continue
                m=metrics(search.render(sim,trial))
                if accepts(current,m,args.objective,mode):
                    retained=trial;current=m;accepted+=1
        info['optimizer']={'baseline':old,'retained':current,'accepted_blocks':accepted,'candidate_evaluations':evaluations,'search_objective':search.OBJECTIVE,'acceptance_objective':args.objective,'passes':args.passes}
        info['optimizer']['search_mode']=mode
        return bytes(v for r in retained for v in r),count,info
    finally:sim.close()
