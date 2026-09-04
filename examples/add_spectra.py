"""Add offline FFT comparisons to an existing cartridge without re-encoding."""
import argparse
from pathlib import Path
from update_comparison import read_entries, build_comparison
from tsaudio.spectrum import attach

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--samples',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--ayumi',type=Path,required=True)
    p.add_argument('--gcc',default='gcc')
    p.add_argument('--pasmo',required=True)
    a=p.parse_args()
    sources={path.stem:path for path in a.samples.glob('*.wav')}
    entries=attach(read_entries(a.base),sources,a.out,a.ayumi,a.gcc)
    m=build_comparison(entries,a.out,a.pasmo)
    print(f"Added {len(entries)} FFT comparisons; {m['payload_bytes']} payload bytes")

if __name__=='__main__':main()
