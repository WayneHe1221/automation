import os
import unittest

from tasks.bushiroad_668 import parse_products as parse_bushiroad_668
from tasks.bushiroad_668 import parse_total
from tasks.shop_watch import (
    SITES,
    is_suspicious_raw_drop,
    parse_cardmax,
    parse_fukufuku,
    parse_fukufuku_count,
    parse_gurapan,
    parse_hobbystation,
    parse_hobbystation_count,
    parse_product_links,
    parse_squarebushi,
    parse_stock_quantity,
    parse_torecolo,
)


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as file:
        return file.read()


class ParserTests(unittest.TestCase):
    def test_squarebushi_parser(self):
        page = load_fixture("squarebushi.html")
        products = parse_squarebushi(page)

        self.assertEqual(parse_total(page), 2)
        self.assertEqual(products["101"]["name"], "Alpha & Beta")
        self.assertTrue(products["101"]["in_stock"])
        self.assertEqual(products["101"]["qty"], 29)
        self.assertFalse(products["102"]["in_stock"])
        self.assertIsNone(products["102"]["qty"])
        self.assertEqual(parse_bushiroad_668(page), products)

    def test_product_link_parser(self):
        products = parse_product_links(load_fixture("product_links.html"))

        self.assertEqual(products["201"]["name"], "First & Card")
        self.assertTrue(products["201"]["in_stock"])
        self.assertEqual(products["201"]["qty"], 12)
        self.assertFalse(products["202"]["in_stock"])
        self.assertIsNone(products["202"]["qty"])

    def test_torecolo_parser(self):
        products = parse_torecolo(load_fixture("torecolo.html"))

        self.assertTrue(products["DECK-WS001"]["in_stock"])
        self.assertEqual(products["DECK-WS001"]["qty"], 7)
        self.assertFalse(products["TCG002"]["in_stock"])
        self.assertIsNone(products["TCG002"]["qty"])

    def test_fukufuku_parser(self):
        page = load_fixture("fukufuku_deck.html")
        products = parse_fukufuku(page)

        self.assertEqual(parse_fukufuku_count(page), 2)
        self.assertEqual(products["501"]["name"], "Fukufuku One")
        self.assertTrue(products["501"]["in_stock"])
        self.assertFalse(products["502"]["in_stock"])

    def test_hobbystation_parser(self):
        page = load_fixture("hobbystation_deck.html")
        products = parse_hobbystation(page)

        self.assertEqual(parse_hobbystation_count(page), 2)
        self.assertEqual(products["601"]["name"], "Hobby One")
        self.assertTrue(products["601"]["in_stock"])
        self.assertEqual(products["601"]["qty"], 3)
        self.assertFalse(products["602"]["in_stock"])
        self.assertIsNone(products["602"]["qty"])

    def test_cardmax_parser(self):
        products = parse_cardmax(load_fixture("cardmax.html"))

        self.assertTrue(products["301"]["in_stock"])
        self.assertEqual(products["301"]["prices"], [1000])
        self.assertFalse(products["302"]["in_stock"])

    def test_cardmax_mobile_parser(self):
        products = parse_cardmax(load_fixture("cardmax_mobile.html"))

        self.assertEqual(products["000000301"]["name"], "Cardmax Mobile One & Bonus")
        self.assertEqual(products["000000301"]["prices"], [4000])
        self.assertTrue(products["000000301"]["in_stock"])
        self.assertFalse(products["000000302"]["in_stock"])

    def test_gurapan_parser(self):
        products = parse_gurapan(load_fixture("gurapan.html"))

        self.assertTrue(products["401"]["in_stock"])
        self.assertEqual(products["401"]["qty"], 4)
        self.assertFalse(products["402"]["in_stock"])
        self.assertIsNone(products["402"]["qty"])

    def test_cardmax_has_no_quantity(self):
        products = parse_cardmax(load_fixture("cardmax.html"))

        self.assertIsNone(products["301"].get("qty"))

    def test_parse_stock_quantity_variants(self):
        self.assertEqual(parse_stock_quantity('<p class="stock">在庫数 29点</p>'), 29)
        self.assertEqual(parse_stock_quantity("在庫数 1,024個"), 1024)
        self.assertEqual(parse_stock_quantity("在庫数：9"), 9)
        self.assertEqual(parse_stock_quantity("在庫数:\n      3"), 3)
        self.assertIsNone(parse_stock_quantity("販売中"))

    def test_raw_drop_guard(self):
        self.assertTrue(is_suspicious_raw_drop(30, 10))
        self.assertFalse(is_suspicious_raw_drop(30, 20))
        self.assertFalse(is_suspicious_raw_drop(3, 1))
        self.assertFalse(is_suspicious_raw_drop(None, 1))

    def test_deck_sources_are_configured(self):
        sites = {site["key"]: site for site in SITES}

        self.assertTrue(
            {
                "fukufuku_deck",
                "torecolo_deck",
                "clabo_deck",
                "hobbystation_deck",
                "gurapan_deck",
                "bushiroad_deck",
            }.issubset(sites)
        )
        self.assertTrue(sites["bushiroad_deck"]["allow_empty"])


if __name__ == "__main__":
    unittest.main()
