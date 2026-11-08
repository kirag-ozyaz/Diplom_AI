from pathlib import Path
import sys

def bootstrap():
    for root in Path(__file__).resolve().parents:
        if (root/'configs/pipeline.json').is_file() and (root/'src/retrieval_eval').is_dir():
            sys.path.insert(0,str(root/'src'))
            return root
    raise RuntimeError('Не найдена папка V2')

bootstrap()
import unittest
from retrieval_eval.scoring import ranked_metrics

class RankMetricTests(unittest.TestCase):
    def test_duplicate_keeps_rank(self):
        self.assertEqual(ranked_metrics(['x','x','y'],{'x':0,'y':2},3,2)['rr'],1/3)
    def test_context_is_not_answer(self):
        self.assertEqual(ranked_metrics(['x'],{'x':1,'y':2},1,2)['hit'],0)
    def test_no_positive(self):
        self.assertIsNone(ranked_metrics(['x'],{'x':0},1,2)['rr'])

if __name__=='__main__':
    unittest.main()
