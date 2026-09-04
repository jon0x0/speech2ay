import math, struct, wave
import numpy as np
AY_LEVELS=np.array([0,836,1212,1773,2619,3875,5397,8823,10392,16706,23339,29292,36969,46421,55195,65535])
AY_SILENCE_LEVEL=11

def read_wav(path):
    with wave.open(str(path), "rb") as w:
        ch, sw, fs = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw == 1:
        x = [(b - 128) / 128.0 for b in raw]
    elif sw == 2:
        a = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        x = [v / 32768.0 for v in a]
    else:
        raise ValueError(f"{path}: use 8- or 16-bit PCM WAV")
    if ch > 1:
        x = [sum(x[i:i + ch]) / ch for i in range(0, len(x), ch)]
    return fs, x

def biquad(x, fs, fc, hp=False):
    q = 0.70710678
    w = 2 * math.pi * fc / fs
    c, s = math.cos(w), math.sin(w)
    a = s / (2 * q)
    if hp:
        b0, b1, b2 = (1 + c) / 2, -(1 + c), (1 + c) / 2
    else:
        b0, b1, b2 = (1 - c) / 2, 1 - c, (1 - c) / 2
    a0, a1, a2 = 1 + a, -2 * c, 1 - a
    b0 /= a0
    b1 /= a0
    b2 /= a0
    a1 /= a0
    a2 /= a0
    x1 = x2 = y1 = y2 = 0.0
    out = []
    for v in x:
        y = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out.append(y)
        x2, x1 = x1, v
        y2, y1 = y1, y
    return out

def resample(x, src, dst):
    n = max(1, int(round(len(x) * dst / src)))
    scale = src / dst
    last = len(x) - 1
    out = []
    for i in range(n):
        p = i * scale
        j = int(p)
        f = p - j
        out.append(x[last] if j >= last else x[j] * (1 - f) + x[j + 1] * f)
    return out
