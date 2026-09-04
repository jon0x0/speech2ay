"""Offline, whole-clip FFT comparison. Cartridge receives only64 bar heights.

Each signal is DC-removed and RMS-normalized before a2048-point Hann Welch
estimate with approximately46ms windows and50% overlap. Original uses its
native rate; the model uses44100Hz.32 logarithmic bands cover80..7000Hz; both panels share
a48dB range relative to their joint peak. This compares spectral shape, not
loudness. Achieved output is modeled, never a hardware recording.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import numpy as np
from .dsp import read_wav, resample, AY_LEVELS
from .codecs import DELTAS
from . import search

def band_power(samples,rate=44100):
    x=np.asarray(samples,dtype=float);x=x-x.mean()
    rms=float(np.sqrt(np.mean(x*x)))
    if rms<1e-10:return np.zeros(32)
    x/=rms
    width=max(64,min(2048,round(rate*2048/44100)));hop=width//2
    x=np.pad(x,(0,max(0,width-len(x))))
    starts=list(range(0,len(x)-width+1,hop))
    if starts[-1]!=len(x)-width:starts.append(len(x)-width)
    window=np.hanning(width)
    power=np.mean([abs(np.fft.rfft(x[i:i+width]*window,2048))**2 for i in starts],axis=0)/(rate*np.sum(window**2))
    frequencies=np.fft.rfftfreq(2048,1/rate);edges=np.geomspace(80,7000,33)
    return np.array([0 if lo>=rate/2 else np.mean(power[(frequencies>=lo)&(frequencies<hi)])
                     if np.any((frequencies>=lo)&(frequencies<hi))
                     else power[np.argmin(abs(frequencies-np.sqrt(lo*hi)))]
                     for lo,hi in zip(edges,edges[1:])])

def dac_wave(entry):
    data=entry['data'];levels=[]
    if entry['codec']=='dpcm3-6k':
        previous=11
        for at in range(0,len(data),3):
            word=int.from_bytes(data[at:at+3],'little')
            for shift in range(0,24,3):
                previous=min(15,max(0,previous+DELTAS[(word>>shift)&7]))
                levels.append(previous)
    else:
        levels=[v for byte in data for v in (byte&15,byte>>4)]
    rate=5000 if entry['codec']=='ay4-5k' else 6000
    # ZOH models the held DAC level, including codec group padding.
    indices=np.minimum((np.arange(round(len(levels)*44100/rate))*rate/44100).astype(int),len(levels)-1)
    x=AY_LEVELS[np.asarray(levels)[indices]].astype(float)/65535
    cutoff=1/(2*np.pi*680000*20e-12);gain=7.8
    k=44100/(np.pi*cutoff);b=1/(1+k);a=(k-1)/(k+1)
    previous=low=0.;output=[]
    for value in x:
        low=b*(value+previous)+a*low;previous=value
        output.append(value/gain+(1-1/gain)*low)
    return np.asarray(output)

def attach(entries,sources,out,ayumi,gcc='gcc'):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    compiler=shutil.which(gcc)
    if not compiler:raise ValueError('Spectrum modeling requires GCC')
    ayumi=Path(ayumi).resolve();exe=(out/'spectrum-worker.exe').resolve()
    subprocess.run([compiler,'-O2','-std=c99','-I'+str(ayumi),str(Path(__file__).with_name('ay_optimizer_worker.c')),str(ayumi/'ayumi.c'),'-lm','-o',str(exe)],check=True)
    env=dict(os.environ);env['PATH']=str(Path(compiler).parent)+os.pathsep+env.get('PATH','')
    sim=search.Simulator(exe,env,1/(2*np.pi*680000*20e-12),7.8)
    originals={};result=[]
    try:
        for entry in entries:
            path=Path(sources[entry['name']])
            if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                raise ValueError('Spectrum source does not match encoded WAV: '+entry['name'])
            if entry['name'] not in originals:
                rate,x=read_wav(path)
                originals[entry['name']]=band_power(x,rate)
            raw=entry['data']
            if entry['codec'] in ('ay4-5k','ay4-6k','dpcm3-6k'):
                wave=dac_wave(entry)
            else:
                wave=search.render(sim,[list(raw[i:i+14]) for i in range(0,len(raw),14)])
            achieved=band_power(wave);original=originals[entry['name']]
            combined=np.r_[original,achieved]
            db=10*np.log10(np.maximum(combined,1e-30)/max(float(combined.max()),1e-30))
            heights=np.rint(np.clip((db+48)/48,0,1)*31).astype(int).tolist() if combined.max()>1e-20 else [0]*64
            result.append(dict(entry,spectrum={'heights':heights,'original_power':original.tolist(),
                'modeled_power':achieved.tolist(),'fft_size':2048,'bands':32,'range_hz':[80,7000],
                'range_db':48,'normalization':'independent RMS, shared peak reference',
                'model':'AYumi or held AY DAC levels, approximate feedback shelf; no speaker model'}))
    finally:sim.close()
    return result
