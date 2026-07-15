import json
import tempfile
import unittest
from pathlib import Path

from lib.catalog import RETIRED_SOURCE_IDS, SOURCE_DEFINITIONS, collect_catalog


class CatalogTests(unittest.TestCase):
    def test_retired_sources_are_not_exported(self):
        active_source_ids = {source["id"] for source in SOURCE_DEFINITIONS}

        self.assertIn("cardshop_serra", RETIRED_SOURCE_IDS)
        self.assertNotIn("cardshop_serra", active_source_ids)

    def test_deck_sources_are_exported(self):
        active_sources = {source["id"]: source for source in SOURCE_DEFINITIONS}

        self.assertTrue(
            {
                "fukufuku_deck",
                "torecolo_deck",
                "clabo_deck",
                "hobbystation_deck",
                "gurapan_deck",
                "bushiroad_deck",
            }.issubset(active_sources)
        )
        self.assertTrue(
            all(
                active_sources[source_id].get("category") == "deck"
                for source_id in active_sources
                if source_id.endswith("_deck")
            )
        )

    def test_catalog_items_include_source_category(self):
        with tempfile.TemporaryDirectory() as directory:
            state_directory = Path(directory, "state")
            state_directory.mkdir()
            Path(state_directory, "shop_watch.json").write_text(
                json.dumps(
                    {
                        "sites": {
                            "torecolo": {"products": {"normal": "一般商品"}},
                            "torecolo_deck": {"products": {"deck": "牌組商品"}},
                        }
                    }
                ),
                encoding="utf-8",
            )

            products, sources = collect_catalog(directory)

        self.assertEqual(
            {"normal": "product", "deck": "deck"},
            {product["productId"]: product["category"] for product in products},
        )
        self.assertEqual(
            {"torecolo": "product", "torecolo_deck": "deck"},
            {source["id"]: source["category"] for source in sources},
        )


if __name__ == "__main__":
    unittest.main()
