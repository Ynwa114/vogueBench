"""Offline regression checks for controlled-vocabulary decoding."""

import json
import unittest

from decode.pipeline import (Decode, DecodeEngine, Garment, coerce, extract_ocr,
                             garment_prompt, load_vocab, mine_caption, to_query)
from decode.providers import MockVision


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

    def test_extract_ocr_keeps_only_expected_literal_fields(self):
        ocr = extract_ocr({"brand": "  DARZI ", "product_title": " Women   Skater Dress ",
                           "price": "₹449", "source_domain": "darzi.in",
                           "evidence": ["DARZI", 449, "Women Skater Dress"]})
        self.assertEqual(ocr.brand, "DARZI")
        self.assertEqual(ocr.product_title, "Women Skater Dress")
        self.assertEqual(ocr.price, "₹449")
        self.assertEqual(ocr.source_domain, "darzi.in")
        self.assertEqual(ocr.evidence, ["DARZI", "Women Skater Dress"])

    def test_garment_prompt_treats_ocr_as_evidence_not_attribute_authority(self):
        prompt = garment_prompt(self.vocab, "onepiece", "red dress", "none")
        self.assertIn("Retailer title, price, and OCR are evidence", prompt)

    def test_decode_preserves_ocr_and_marks_ocr_brand_source(self):
        scene = {"people": 1, "garments": [{"role": "onepiece", "locator": "red dress", "visibility": "full"}],
                 "ocr": {"brand": "DARZI", "product_title": "Women Skater Multicolor Dress",
                         "price": "₹449", "source_domain": "darzi.in", "evidence": ["DARZI", "₹449"]}}
        garment = {"category": {"value": "dress", "confidence": 1.0},
                   "search_phrase": "red skater dress"}
        engine = DecodeEngine(MockVision({"0": json.dumps(scene), "1": json.dumps(garment)}), self.vocab)
        decoded = engine.decode(b"not-an-image")
        self.assertEqual(decoded.ocr.brand, "DARZI")
        self.assertEqual(decoded.ocr.price, "₹449")
        self.assertEqual(decoded.garments[0].brand, "DARZI")
        self.assertEqual(decoded.garments[0].brand_source, "ocr")

    def test_query_bridge_omits_solid_pattern(self):
        garment = Garment("top")
        garment.attrs = {"colour": type("A", (), {"value": "black"})(), "pattern": type("A", (), {"value": "solid"})(), "fabric_look": type("A", (), {"value": "satin_look"})(), "silhouette": type("A", (), {"value": "fitted"})(), "length": type("A", (), {"value": "waist"})(), "category": type("A", (), {"value": "top"})()}
        self.assertEqual(to_query(Decode("x", [garment])), "black satin look fitted waist top")


if __name__ == "__main__":
    unittest.main()
