"""Offline regression checks for the decode scoring gate."""

import unittest

from decode.pipeline import coerce, load_vocab
from eval.score import field_score, score_look, summarise


class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocab()

    def test_near_colour_receives_partial_credit(self):
        self.assertEqual(field_score(self.vocab, "colour", "navy", "black"), 0.5)

    def test_empty_surface_detail_is_equivalent_to_explicit_none(self):
        self.assertEqual(field_score(self.vocab, "surface_detail", [], ["none"]), 1.0)
        self.assertEqual(field_score(self.vocab, "surface_detail", ["none"], []), 1.0)
        value, clean = coerce(self.vocab, "surface_detail", [])
        self.assertTrue(clean)
        self.assertEqual(value, ["none"])

    def test_wrong_category_is_a_hard_failure(self):
        gold = {"image_id": "look-1", "garments": [{"role": "onepiece", "category": "dress", "colour": "black"}]}
        pred = {"garments": [{"role": "onepiece", "category": "trousers", "colour": "black", "_conf": {"category": 0.9}}]}
        result = score_look(self.vocab, pred, gold)
        self.assertEqual(result.hard_fails, 1)
        self.assertEqual(result.score, 0.0)

    def test_good_high_confidence_run_passes_gate(self):
        gold = {"image_id": "look-1", "garments": [{"role": "onepiece", "category": "dress", "colour": "black"}]}
        pred = {"garments": [{"role": "onepiece", "category": "dress", "colour": "black", "_conf": {"category": 0.9, "colour": 0.9}}]}
        summary = summarise("mock", [score_look(self.vocab, pred, gold)])
        self.assertTrue(summary.gate()[0], summary.gate()[1])


if __name__ == "__main__":
    unittest.main()
