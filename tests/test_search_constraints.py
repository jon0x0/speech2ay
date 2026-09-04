import unittest
from tsaudio.search import candidates
from tsaudio.optimizer import accepts


class ConservativeSearchTests(unittest.TestCase):
    def test_spectral_gain_cannot_buy_roughness_or_periodicity_regression(self):
        old={'spectrum':.2053,'waveform':.5885,'periodicity':.0311,'roughness':.0236}
        trial={'spectrum':.1357,'waveform':.5751,'periodicity':.0304,'roughness':.0673}
        self.assertTrue(accepts(old,trial,'joint','free'))
        self.assertFalse(accepts(old,trial,'joint','conservative'))
        trial['roughness']=.02
        self.assertTrue(accepts(old,trial,'joint','conservative'))
        trial['periodicity']=.04
        self.assertFalse(accepts(old,trial,'joint','conservative'))
        self.assertFalse(accepts(old,trial,'spectrum','conservative'))

    def test_repeated_passes_stay_within_original_voice_bounds(self):
        anchor=[126,4,52,0,50,0,5,56,11,9,8,1,0,255]
        seed=anchor.copy()
        # Exercise a candidate at the upper boundary as a later-pass seed.
        p=int((anchor[0]+256*anchor[1])*1.06)
        seed[:2]=[p&255,p>>8]
        rows=candidates(seed,[1]*14,96,anchor=anchor)
        self.assertGreater(len(rows),16)
        for row in rows:
            self.assertEqual(row[6:8],anchor[6:8])
            self.assertEqual(row[11:14],anchor[11:14])
            for ch in range(3):
                original=anchor[2*ch]+256*anchor[2*ch+1]
                period=row[2*ch]+256*row[2*ch+1]
                self.assertLessEqual(abs(period/original-1),.06000001)
                self.assertIn(row[8+ch],range(16))

    def test_noise_can_change_without_enabling_muted_voices(self):
        anchor=[1,0,1,0,1,0,5,31,0,0,9,1,0,255]
        rows=candidates(anchor,anchor,96,anchor=anchor)
        self.assertEqual({r[6] for r in rows},set(range(1,32)))
        self.assertTrue(all(r[8:10]==[0,0] and r[7]==31 for r in rows))

    def test_free_search_retains_envelope_candidates(self):
        seed=[126,4,52,0,50,0,5,56,11,9,8,1,0,255]
        self.assertTrue(any(16 in r[8:11] for r in candidates(seed,seed,96)))


if __name__=='__main__':unittest.main()
