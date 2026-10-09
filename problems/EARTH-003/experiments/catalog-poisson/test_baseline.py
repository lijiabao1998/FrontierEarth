import copy
import math
import random
import unittest
import baseline as b

def fixture(**changes):
    row=dict(id='x',time='2017-01-01T00:00:00Z',latitude='32',longitude='-125',depth='-100',mag='4.0',type='earthquake');row.update(changes);return row

class Controls(unittest.TestCase):
 def test_half_score(self):
    s=b.score([0,1],.5);self.assertEqual(s['brier'],.25);self.assertAlmostEqual(s['log_loss'],math.log(2))
 def test_perfect_and_opposite(self):
    self.assertEqual(b.score([0,0],0)['brier'],0);self.assertEqual(b.score([1,1],0)['brier'],1)
    self.assertTrue(math.isfinite(b.score([1,1],0)['log_loss']))
 def test_rate_not_active_days(self):
    f=b.fit([2,0]);self.assertEqual(f['lambda_events_per_day'],1);self.assertAlmostEqual(f['poisson'],1-math.exp(-1));self.assertEqual(f['bernoulli_climatology'],.5)
 def test_empty_calibration_rejected(self):
    with self.assertRaises(ValueError):b.fit([0,0])
 def test_edges(self):
    events,excluded=b.parse_rows([fixture(),fixture(id='y',latitude='42',longitude='-114',depth='1000',time='2018-01-01T00:00:00Z')]);self.assertEqual(len(events),2);counts=b.daily(events);self.assertEqual(counts[0],1);self.assertEqual(counts[365],1);self.assertEqual(sum(counts),2)
 def test_time_endpoint_exclusive(self):
    events,excluded=b.parse_rows([fixture(time='2019-01-01T00:00:00Z')]);self.assertFalse(events);self.assertEqual(excluded,['x'])
 def test_before_start(self):
    events,_=b.parse_rows([fixture(time='2016-12-31T23:59:59.999Z')]);self.assertFalse(events)
 def test_magnitude_boundary(self):
    events,_=b.parse_rows([fixture(mag='3.999')]);self.assertFalse(events)
 def test_duplicate_rejected(self):
    with self.assertRaises(ValueError):b.parse_rows([fixture(),fixture()])
 def test_missing_nonfinite_rejected(self):
    for x in ('','nan','inf','-inf'):
      with self.assertRaises(ValueError):b.parse_rows([fixture(mag=x)])
 def test_timezone_required(self):
    with self.assertRaises(ValueError):b.parse_rows([fixture(time='2017-01-01T00:00:00')])
 def test_block_boundaries(self):
    ix=b.block_indices(365,random.Random(196003));self.assertEqual(len(ix),365);self.assertTrue(all(0<=x<365 for x in ix));self.assertTrue(all((ix[i]+1)%365==ix[i+1] for i in range(29)))
 def test_quantile(self):self.assertEqual(b.quantile([0,10],.25),2.5)
 def test_mutant_rejected(self):
    with self.assertRaises(AssertionError):self.assertEqual(0.0,b.score([0,1],.5)['brier'])

if __name__=='__main__':unittest.main(verbosity=2)
