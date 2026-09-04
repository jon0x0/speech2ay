"""Reduced-channel synthesis must retain unvoiced consonant/noise energy."""
import sys,tempfile,unittest,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.codecs import encode
class CodecTests(unittest.TestCase):
    def test_noise_survives_reduced_channels(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'noise.wav'
            noise=(np.random.default_rng(4).normal(0,3000,4000)).clip(-32768,32767).astype('<i2')
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(noise.tobytes())
            for channels in (1,2,3):
                raw,count,_=encode(path,f'harmonic{channels}')
                rows=np.frombuffer(raw,dtype=np.uint8).reshape(count,14)
                self.assertTrue(any(r[8+channels-1]>0 and not r[7]&(1<<(channels+2)) for r in rows))
                self.assertTrue(all(not any(r[8+channels:11]) for r in rows))
if __name__=='__main__':unittest.main()
