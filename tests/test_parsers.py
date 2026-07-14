import os
import unittest

from tasks.bushiroad_668 import parse_products as parse_bushiroad_668
from tasks.bushiroad_668 import parse_total
from tasks.shop_watch import (
    is_suspicious_raw_drop,
    parse_cardmax,
    parse_gurapan,
    parse_product_links,
    parse_squarebushi,
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
        self.assertFalse(products["102"]["in_stock"])
        self.assertEqual(parse_bushiroad_668(page), products)

    def test_product_link_parser(self):
        products = parse_product_links(load_fixture("product_links.html"))

        self.assertEqual(products["201"]["name"], "First & Card")
        self.assertTrue(products["201"]["in_stock"])
        self.assertFalse(products["202"]["in_stock"])

    def test_torecolo_parser(self):
        products = parse_torecolo(load_fixture("torecolo.html"))

        self.assertTrue(products["TCG001"]["in_stock"])
        self.assertFalse(products["TCG002"]["in_stock"])

    def test_cardmax_parser(self):
        products = parse_cardmax(load_fixture("cardmax.html"))

        self.assertTrue(products["301"]["in_stock"])
        self.assertFalse(products["302"]["in_stock"])

    def test_gurapan_parser(self):
        products = parse_gurapan(load_fixture("gurapan.html"))

        self.assertTrue(products["401"]["in_stock"])
        self.assertFalse(products["402"]["in_stock"])

    def test_raw_drop_guard(self):
        self.assertTrue(is_suspicious_raw_drop(30, 10))
        self.assertFalse(is_suspicious_raw_drop(30, 20))
        self.assertFalse(is_suspicious_raw_drop(3, 1))
        self.assertFalse(is_suspicious_raw_drop(None, 1))


if __name__ == "__main__":
    unittest.main()
