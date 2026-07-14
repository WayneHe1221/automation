import unittest

from lib.catalog import RETIRED_SOURCE_IDS, SOURCE_DEFINITIONS


class CatalogTests(unittest.TestCase):
    def test_retired_sources_are_not_exported(self):
        active_source_ids = {source["id"] for source in SOURCE_DEFINITIONS}

        self.assertIn("cardshop_serra", RETIRED_SOURCE_IDS)
        self.assertNotIn("cardshop_serra", active_source_ids)

    def test_deck_sources_are_exported(self):
        active_source_ids = {source["id"] for source in SOURCE_DEFINITIONS}

        self.assertTrue(
            {
                "fukufuku_deck",
                "torecolo_deck",
                "clabo_deck",
                "hobbystation_deck",
                "gurapan_deck",
                "bushiroad_deck",
            }.issubset(active_source_ids)
        )


if __name__ == "__main__":
    unittest.main()
