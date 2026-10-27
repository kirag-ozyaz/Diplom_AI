import math, unittest
from rank_metrics import *
from eval_retrieval_rank import rank_info, parse_args

class T(unittest.TestCase):
    def test_basic(self):
        m = summarize_ranks([1, 2, None, 4], (1, 3, 5, 10), 10)
        self.assertAlmostEqual(m["hit@1"], .25); self.assertAlmostEqual(m["hit@3"], .5); self.assertAlmostEqual(m["hit@5"], .75)
        self.assertAlmostEqual(m["mrr"], (1 + .5 + 0 + .25) / 4)
        self.assertAlmostEqual(m["mrr@3"], 1.5 / 4)
        self.assertAlmostEqual(m["ndcg@1"], .25)
        self.assertAlmostEqual(m["ndcg@5"], (1 + 1 / math.log2(3) + 1 / math.log2(5)) / 4)
    def test_ndcg_consistency(self):
        for r in range(1, 11):
            rels = [0] * 10; rels[r - 1] = 1
            for k in (1, 3, 5, 10):
                self.assertAlmostEqual(ndcg_at_k(rels, k, 1), ndcg_from_rank(r, k))
    def test_multi(self):
        self.assertAlmostEqual(ndcg_at_k([1, 1, 0], 3, 2), 1.0)
        self.assertAlmostEqual(ndcg_at_k([0, 1, 1], 3, 2), (1/math.log2(3)+.5)/(1+1/math.log2(3)))
    def test_bounds(self):
        d = [{"hit": {"@1": True, "@3": True, "@5": True}}, {"hit": {"@1": False, "@3": True, "@5": True}},
             {"hit": {"@1": False, "@3": False, "@5": False}}]
        b = bounds_from_hits(d)
        self.assertAlmostEqual(b["mrr"][0], (1 + 1/3) / 3); self.assertAlmostEqual(b["mrr"][1], (1 + .5 + 1/6) / 3)
        self.assertEqual(b["hit@5"][0], b["hit@5"][1])
    def test_rank_info(self):
        res = [{"text": "Пункт 1.2.7 ..."}, {"text": "п. 1.2.6 опред."}, {"text": "1.2.6 ещё"}]
        self.assertEqual(rank_info(res, "1.2.6")["rank"], 2)
        r = rank_info(res, ["1.2.6", "1.2.7"], dedup=True); self.assertEqual(r["rels"], [1, 1, 0])
        self.assertIsNone(rank_info(res, "9.9.9")["rank"])
    def test_args(self):
        a = parse_args(["--mode", "rerank"]); self.assertEqual(a.k_max, 10); self.assertTrue(str(a.out).endswith("stage4_rank_results_rerank.json"))

unittest.main(verbosity=1)
