"""Prepare the four comparison clips from an existing local WAV collection."""
import argparse
import shutil
import sys
import wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tsaudio.dsp import read_wav, resample

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--gap-ms', type=float, default=100)
    parser.add_argument('--wargames', type=Path, help='Optional Shall we play a game WAV, replacing Effect 31')
    args = parser.parse_args()
    if args.gap_ms < 0:
        parser.error('--gap-ms must be nonnegative')
    args.out.mkdir(parents=True, exist_ok=True)
    pieces = []
    for name in ['18.wav', '08.wav']:
        rate, samples = read_wav(args.samples / name)
        if not samples:
            parser.error(f'{name} is empty')
        pieces.append(np.asarray(resample(samples, rate, 16000)))
    joined = np.concatenate([pieces[0], np.zeros(round(args.gap_ms * 16)), pieces[1]])
    pcm = np.clip(np.rint(joined * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(args.out / 'Intruder Alert.wav'), 'wb') as output:
        output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        output.writeframes(pcm.tobytes())
    clips=[('15.wav', 'Humanoid'), ('30.wav', 'Laser')]
    if not args.wargames:
        clips.append(('31.wav', 'Effect 31'))
    for source, title in clips:
        shutil.copy2(args.samples / source, args.out / (title + '.wav'))
    if args.wargames:
        shutil.copy2(args.wargames, args.out / 'Shall we play a game.wav')
    print(args.out.resolve())

if __name__ == '__main__':
    main()
