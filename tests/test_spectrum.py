"""FFT plot checks independent of the cartridge bar renderer."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tsaudio.spectrum import band_power

class SpectrumTests(unittest.TestCase):
    def test_known_tones_land_in_expected_log_bands(self):
        time=np.arange(44100)/44100
        edges=np.geomspace(80,7000,33)
        for hz in (440,1000,3000):
            peak=int(np.argmax(band_power(np.sin(2*np.pi*hz*time))))
            self.assertLessEqual(edges[peak],hz)
            self.assertGreater(edges[peak+1],hz)

    def test_shape_is_independent_of_gain_and_dc(self):
        signal=np.sin(2*np.pi*1000*np.arange(12000)/44100)
        np.testing.assert_allclose(band_power(signal),band_power(.2*signal+4),rtol=1e-7,atol=1e-10)

    def test_silence_has_no_power(self):
        np.testing.assert_array_equal(band_power(np.ones(5000)),np.zeros(32))

    def test_source_has_no_spectrum_above_its_nyquist(self):
        rate=8000
        power=band_power(np.sin(2*np.pi*1000*np.arange(rate)/rate),rate)
        edges=np.geomspace(80,7000,33)
        self.assertTrue(all(power[edges[:-1]>=rate/2]==0))

if __name__=='__main__':unittest.main()
