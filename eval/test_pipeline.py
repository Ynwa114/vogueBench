"""Offline regression checks for controlled-vocabulary decoding."""

import unittest

from decode.pipeline import Decode, DecodeEngine, Garment, coerce, load_vocab, mine_caption, to_query


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vocab = load_vocab()

    def test_coerce_rejects_unknown_values(self):
        value, clean = coerce(self.vocab, "colour", "ultraviolet")
        self.assertIsNone(value)
        self.assertFalse(clean)

    def test_coerce_normalises_valid_values(self):
        value, clean = coerce(self.vocab, "fabric_look", "Satin Look")
        self.assertEqual(value, "satin_look")
        self.assertTrue(clean)

    def test_caption_mining_uses_known_brand_casing(self):
        mined = mine_caption("Dress from @zaraindia #weekend", {"Zara India"})
        self.assertEqual(mined["brand_candidates"], ["Zara India"])

    def test_query_bridge_omits_solid_pattern(self):
        garment = Garment("top")
        garment.attrs = {"colour": type("A", (), {"value": "black"})(), "pattern": type("A", (), {"value": "solid"})(), "fabric_look": type("A", (), {"value": "satin_look"})(), "silhouette": type("A", (), {"value": "fitted"})(), "length": type("A", (), {"value": "waist"})(), "category": type("A", (), {"value": "top"})()}
        self.assertEqual(to_query(Decode("x", [garment])), "black satin look fitted waist top")


if __name__ == "__main__":
    unittest.main()
