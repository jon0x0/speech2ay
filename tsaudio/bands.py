import math
import numpy as np
CLOCK=1764750
LEVELS=np.array([0,.00999466,.01445029,.02105745,.03070115,.04554818,.06449989,.10736248,.12658885,.20498970,.29221027,.37283894,.49253071,.63532464,.8055848,1])

def encode(x, rate, hz, noise, clock=CLOCK):
    # 32ms centered Hann analysis; 60/120Hz updates do not alter word speed.
    width = int(rate * .032) | 1
    window = np.hanning(width)
    nfft = 1 << (width * 4 - 1).bit_length()
    freq = np.fft.rfftfreq(nfft, 1/rate)
    bands = [(180, 900), (900, 2200), (2200, 4500)]
    padded = np.pad(x, (width//2, width))
    previous = [None]*3
    result, features = [], []
    reference = max(float(np.sqrt(np.mean(x*x))), 1e-9)
    for step in range(math.ceil(len(x)/rate*hz)):
        center = round((step + .5)*rate/hz)
        chunk = padded[center:center+width]
        chunk = np.pad(chunk, (0, max(0, width-len(chunk))))
        chunk = chunk - chunk.mean()
        rms = float(np.sqrt(np.mean(chunk*chunk)))
        spectrum = abs(np.fft.rfft(chunk*window, nfft))
        # Smooth across ~140Hz: favor broad spectral concentrations, not isolated bins.
        smoothing = max(3, round(140/(rate/nfft)))
        envelope = np.convolve(spectrum, np.ones(smoothing)/smoothing, 'same')
        ac = np.correlate(chunk*window, chunk*window, 'full')[width-1:]
        periodicity = float(max(ac[int(rate/400):int(rate/75)], default=0)/(ac[0]+1e-12))
        high = float(np.sum(spectrum[freq > 2000]**2)/(np.sum(spectrum**2)+1e-12))
        # Conservative heuristic, deliberately exposed for later listening-led tuning.
        unvoiced = noise and periodicity < .48 and high > .18
        regs = [0]*11
        regs[6], regs[7] = 5, 0x38  # Noise disabled initially; I/O bits left out of preview.
        energies = []
        for lo, hi in bands:
            mask = (freq >= lo) & (freq < min(hi, rate/2))
            energies.append(float(np.sqrt(np.sum(spectrum[mask]**2))))
        norm = max(energies + [1e-12])
        for ch, (lo, hi) in enumerate(bands):
            indices = np.flatnonzero((freq >= lo) & (freq < min(hi, rate/2)))
            score = envelope[indices].copy()
            if previous[ch] is not None:
                # Mild continuity preference; retain fast consonant/vowel transitions.
                score *= 1 + .25*np.exp(-.5*((freq[indices]-previous[ch])/180)**2)
            chosen = float(freq[indices[np.argmax(score)]])
            previous[ch] = chosen
            period = int(np.clip(round(clock/(16*chosen)), 1, 4095))
            regs[ch*2], regs[ch*2+1] = period & 255, period >> 8
            amplitude = min(.85, rms/reference*.35) * (energies[ch]/norm)**.65
            if rms < reference*.045:
                amplitude = 0
            if unvoiced:
                # One shared noise source, on C only; avoid three copies of identical noise.
                amplitude = min(.65, rms/reference*.45) if ch == 2 else 0
                regs[7] = 0x1f  # All tones off, noise on C.
            if rms < reference*.045:
                amplitude = 0
            regs[8+ch] = int(np.argmin(abs(LEVELS-amplitude)))
        result.append(regs)
        features.append({'rms': rms, 'periodicity': periodicity, 'high_energy': high, 'noise': bool(unvoiced)})
    return result, features
