import json
import tempfile
import types
import unittest
from pathlib import Path

from lib.catalog import RETIRED_SOURCE_IDS, SOURCE_DEFINITIONS, collect_catalog
from tasks.bushiroad_668 import LIST_URL as BUSHIROAD_668_LIST_URL
from tasks.shop_watch import SITES


def _fetched_urls(code):
    """從抓取 lambda 的常數中取出網址字面值（含巢狀 code object）。"""
    urls = set()
    for constant in code.co_consts:
        if isinstance(constant, str) and constant.startswith("http"):
            urls.add(constant)
        elif isinstance(constant, types.CodeType):
            urls |= _fetched_urls(constant)
    return urls


class CatalogTests(unittest.TestCase):
    def test_every_source_declares_its_watched_page(self):
        for definition in SOURCE_DEFINITIONS:
            with self.subTest(source=definition["id"]):
                self.assertTrue(definition["page_url"].startswith("https://"))

    def test_page_url_matches_the_url_the_task_actually_fetches(self):
        """展示用的原始連結必須是真正被監看的列表頁，避免兩邊各自改動而失準。"""
        page_urls = {
            definition["id"]: definition["page_url"] for definition in SOURCE_DEFINITIONS
        }

        self.assertEqual(BUSHIROAD_668_LIST_URL, page_urls["bushiroad_668"])
        for site in SITES:
            with self.subTest(site=site["key"]):
                self.assertIn(page_urls[site["key"]], _fetched_urls(site["fetch"].__code__))

    def test_collect_catalog_exports_page_url(self):
        with tempfile.TemporaryDirectory() as directory:
            state_directory = Path(directory, "state")
            state_directory.mkdir()
            Path(state_directory, "shop_watch.json").write_text(
                json.dumps({"sites": {"gurapan": {"products": {"1": "商品"}}}}),
                encoding="utf-8",
            )

            _products, sources = collect_catalog(directory)

        self.assertEqual(
            "https://gurapan.jp/products/list?category_id=1081", sources[0]["pageUrl"]
        )

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
                            "cardmax": {
                                "products": {
                                    "priced": {"name": "有價格商品", "prices": [4000]}
                                }
                            },
                            "manasource": {
                                "products": {
                                    "stocked": {"name": "有庫存商品", "qty": 12},
                                    "stocked2": {"name": "有庫存商品二", "qty": 8},
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            products, sources = collect_catalog(directory)

        self.assertEqual(
            {
                "normal": "product",
                "deck": "deck",
                "priced": "product",
                "stocked": "product",
                "stocked2": "product",
            },
            {product["productId"]: product["category"] for product in products},
        )
        self.assertEqual(
            {
                "torecolo": "product",
                "torecolo_deck": "deck",
                "cardmax": "product",
                "manasource": "product",
            },
            {source["id"]: source["category"] for source in sources},
        )
        priced_product = next(
            product for product in products if product["productId"] == "priced"
        )
        self.assertEqual(priced_product["prices"], [4000])
        self.assertIsNone(priced_product["qty"])

        by_id = {product["productId"]: product for product in products}
        self.assertEqual(by_id["stocked"]["qty"], 12)
        self.assertIsNone(by_id["normal"]["qty"])

        source_stock = {source["id"]: source["stockQuantity"] for source in sources}
        self.assertEqual(source_stock["manasource"], 20)
        self.assertEqual(source_stock["torecolo"], 0)


if __name__ == "__main__":
    unittest.main()
