"""Deterministic encoders. No game assets or sibling imports required."""
import math
import numpy as np
from .dsp import read_wav, biquad, resample, AY_LEVELS
from . import bands, harmonic

DELTAS = (-4, -2, -1, 0, 1, 2, 4, 8)
CODECS = ('ay4-5k', 'ay4-6k', 'dpcm3-6k', 'harmonic1', 'harmonic2', 'harmonic3')

def source(path, low=80, high=6500):
    rate, x = read_wav(path)
    if not x or rate < 4000:
        raise ValueError('Use a nonempty PCM WAV at 4000 Hz or higher')
    if not 0 < low < high:
        raise ValueError('Require 0 < low cutoff < high cutoff')
    x = np.asarray(x, dtype=float)
    x -= x.mean()
    x = biquad(x, rate, min(low, rate*.4), True)
    cutoff = min(high, rate*.43)
    x = biquad(biquad(x, rate, cutoff), rate, cutoff)
    return rate, np.asarray(x)

def encode(path, codec, low=80, high=6500, profile='filtered'):
    if codec.startswith('harmonic') and profile=='berzerk':
        rate,x=read_wav(path);x=np.asarray(x,dtype=float)
        if not len(x) or rate<4000:raise ValueError('Use a nonempty PCM WAV at 4000 Hz or higher')
    else:
        rate, x = source(path, low, high)
    original_seconds = len(x)/rate
    if codec.startswith('harmonic'):
        channels = int(codec[-1])
        analysis = harmonic.pitch_analysis(x, rate)
        baseline, _ = bands.encode(x, rate, harmonic.HZ, True, clock=1774400 if profile=='berzerk' else 1764750)
        rows = harmonic.harmonic_encode(x, rate, baseline, analysis, channels=channels)
        for r in rows:
            # The legacy unvoiced model uses noise on C. Route that shared
            # noise voice onto the last available channel in reduced modes.
            if channels < 3 and r[7] == 0x1f:
                volume = r[10]
                r[8:11] = [0,0,0]
                r[8+channels-1] = volume
                r[7] = 63 ^ (1 << (channels+2))
            for c in range(channels, 3):
                r[8+c] = 0
                r[7] |= (1 << c) | (1 << (c+3))
        raw = bytes(v for r in rows for v in r+[1,0,255])
        return raw, len(rows), {'seconds':len(rows)/harmonic.HZ, 'source_seconds':original_seconds,
                               'channels':channels, 'analysis':analysis, 'profile':profile}
    hz = 5000 if codec == 'ay4-5k' else 6000
    # Anti-alias before rate reduction; preserve silence and clip boundaries.
    cutoff = min(hz*.43, high, rate*.43)
    x = biquad(biquad(x, rate, cutoff), rate, cutoff)
    x = np.asarray(resample(x, rate, hz))
    x *= .96 / max(float(np.max(abs(x))), 1e-12)
    center = AY_LEVELS[11]
    target = center + x*np.where(x >= 0, 65535-center, center)
    q = np.argmin(abs(target[:,None]-AY_LEVELS),axis=1).tolist()
    exact = len(q)
    group = 8 if codec.startswith('dpcm') else (10 if hz == 5000 else 2)
    q += [11]*((-len(q)) % group)
    if codec.startswith('dpcm'):
        previous = 11
        codes = []
        for level in q:
            options = [min(15,max(0,previous+d)) for d in DELTAS]
            k = min(range(8), key=lambda i:abs(int(AY_LEVELS[options[i]])-int(AY_LEVELS[level])))
            previous = options[k]
            codes.append(k)
        raw = b''.join(sum(codes[i+j] << (3*j) for j in range(8)).to_bytes(3,'little')
                       for i in range(0,len(codes),8))
    else:
        raw = bytes(q[i] | (q[i+1]<<4) for i in range(0,len(q),2))
    return raw, len(q)//group, {'seconds':len(q)/hz, 'source_seconds':original_seconds,
                              'samples':exact, 'padded_samples':len(q), 'rate':hz}
