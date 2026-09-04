import math
import numpy as np
from . import bands as speech
HZ=60.1145
AY_CLOCK=1764750

def pitch_analysis(x, rate):
    """Normalized autocorrelation with local maxima and a mild continuity bias.
    Pitch is an estimate, not a TSI phone decode; confidence accompanies every frame.
    """
    width = int(rate*.055) | 1
    padded = np.pad(x, (width//2, width))
    result = []
    previous = None
    for i in range(math.ceil(len(x)/rate*HZ)):
        center = round((i+.5)*rate/HZ)
        y = padded[center:center+width]
        y = np.pad(y,(0,max(0,width-len(y))))
        y = y-y.mean()
        nfft = 8192
        spec = abs(np.fft.rfft(y*np.hanning(width),nfft))
        frequencies = np.fft.rfftfreq(nfft,1/rate)
        lags = np.arange(int(rate/400),int(rate/70)+1)
        corr = np.array([np.dot(y[:-k],y[k:]) /
                         (np.linalg.norm(y[:-k])*np.linalg.norm(y[k:])+1e-15) for k in lags])
        peaks = np.flatnonzero((corr[1:-1]>=corr[:-2]) & (corr[1:-1]>corr[2:]))+1
        if len(peaks):
            best = max(corr[peaks])
            candidates = peaks[corr[peaks]>=best-.08]
            scores = corr[candidates].copy()
            if previous:
                scores -= .08*abs(np.log2((rate/lags[candidates])/previous))
            chosen = candidates[np.argmax(scores)]
            f0, confidence = rate/lags[chosen], max(0,float(corr[chosen]))
        else:
            f0, confidence = 0.,0.
        if confidence > .55:
            previous = f0
        power = spec*spec
        centroid = float(np.sum(frequencies*power)/(sum(power)+1e-15))
        result.append({'time_seconds':(i+.5)/HZ, 'f0_hz':float(f0),
                       'confidence':confidence,'rms':float(np.sqrt(np.mean(y*y))),
                       'spectral_centroid_hz':centroid})
    return result

def harmonic_encode(x, rate, baseline, analysis, channels=3):
    """Fit three AY square-wave spectral templates on a source-pitch harmonic grid.
    Accounts for each square wave's odd harmonics. This is magnitude-only fitting;
    it cannot restore arbitrary phase/formants with just three channels.
    """
    result = []
    width = int(rate*.04) | 1
    padded = np.pad(x,(width//2,width))
    nfft = 4096
    freq = np.fft.rfftfreq(nfft,1/rate)
    keep = (freq>=80)&(freq<=min(6500,rate/2))
    freq = freq[keep]
    reference = max(np.sqrt(np.mean(x*x)),1e-10)
    for i, (base, item) in enumerate(zip(baseline,analysis)):
        regs = base.copy()
        if item['confidence'] < .55 or item['rms'] < reference*.06:
            result.append(regs)
            item['harmonic_fit'] = False
            continue
        center = round((i+.5)*rate/HZ)
        y = padded[center:center+width]
        y = np.pad(y,(0,max(0,width-len(y))))
        target = abs(np.fft.rfft((y-y.mean())*np.hanning(width),nfft))[keep]
        target = np.convolve(target, np.ones(5)/5, 'same')
        f0 = item['f0_hz']
        fundamental_candidates = f0*np.arange(1,min(24,int(4000/f0))+1)
        templates = []
        for f in fundamental_candidates:
            template = np.zeros_like(freq)
            for harmonic in range(1,int(6500/f)+1,2):
                template += np.exp(-.5*((freq-harmonic*f)/45)**2)/harmonic
            templates.append(template)
        dictionary = np.array(templates).T
        residual = target.copy()
        chosen = []
        gains = np.zeros(channels)
        for channel in range(channels):
            scores = dictionary.T@residual / np.sqrt(np.sum(dictionary*dictionary,axis=0)+1e-15)
            scores[chosen] = -np.inf
            chosen.append(int(np.argmax(scores)))
            gains = np.maximum(0,np.linalg.lstsq(dictionary[:,chosen],target,rcond=None)[0])
            residual = target-dictionary[:,chosen]@gains
        order = np.argsort(fundamental_candidates[chosen])
        chosen = np.array(chosen)[order]
        gains = gains[order]
        regs[7] = 0x38
        for ch, index in enumerate(chosen):
            period = int(np.clip(round(AY_CLOCK/(16*fundamental_candidates[index])),1,4095))
            regs[ch*2:ch*2+2] = [period&255,period>>8]
            amplitude = min(.8,item['rms']/reference*.4)*gains[ch]/max(max(gains),1e-12)
            regs[8+ch] = int(np.argmin(abs(speech.LEVELS-amplitude)))
        item['harmonic_fit'] = True
        item['selected_harmonics'] = [int(k)+1 for k in chosen]
        item['relative_spectral_error'] = float(np.linalg.norm(residual)/(np.linalg.norm(target)+1e-15))
        result.append(regs)
    return result
