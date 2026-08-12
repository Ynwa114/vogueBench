"""Offline regression checks for symbolic constraints and query telemetry."""

import unittest

from decode.pipeline import load_vocab
from decode.predicates import load_predicates, parse_query, validate_predicates


class PredicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocab()
        cls.predicates = load_predicates(vocab=cls.vocab)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(field["weight"] for field in self.vocab["fields"].values()), 1.0)

    def test_every_predicate_grounding_references_schema_values(self):
        validate_predicates(self.vocab, self.predicates)

    def test_negated_colour_is_an_exact_exclusion(self):
        state = parse_query("black dress, not beige", self.vocab, self.predicates)
        self.assertEqual(state.exclude_attrs["colour"], ["beige"])
        self.assertNotIn("beige", state.gate["colour"])

    def test_word_boundaries_do_not_match_inside_words(self):
        state = parse_query("that ruched dress", self.vocab, self.predicates)
        self.assertNotIn("hat", state.gate.get("category", []))
        self.assertNotIn("red", state.gate.get("colour", []))

    def test_exclusion_cannot_be_relaxed_by_admission(self):
        state = parse_query("dress, not too revealing", self.vocab, self.predicates)
        revealing = {"category": "dress", "sheerness": "sheer"}
        opaque = {"category": "dress", "sheerness": "opaque"}
        self.assertFalse(state.admits(revealing, self.predicates))
        self.assertTrue(state.admits(opaque, self.predicates))

    def test_nothing_sheer_does_not_exclude_opaque_chiffon_look(self):
        state = parse_query("dress, nothing sheer", self.vocab, self.predicates)
        opaque_chiffon = {"category": "dress", "sheerness": "opaque", "fabric_look": "chiffon_look"}
        semi_sheer = {"category": "dress", "sheerness": "semi_sheer"}
        self.assertTrue(state.admits(opaque_chiffon, self.predicates))
        self.assertFalse(state.admits(semi_sheer, self.predicates))


if __name__ == "__main__":
    unittest.main()
