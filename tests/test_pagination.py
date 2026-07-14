import unittest
from unittest import mock

from tasks.shop_watch import fetch_paged


def parse_fake_products(page):
    products = {}
    for line in page.splitlines():
        if line.startswith("product:"):
            product_id = line.split(":", 1)[1]
            products[product_id] = {"name": product_id, "in_stock": True}
    return products


class PaginationTests(unittest.TestCase):
    @mock.patch("tasks.shop_watch.fetch_html")
    def test_incomplete_pagination_raises(self, fetch):
        fetch.side_effect = [
            '<div class="count_number"><span class="number">3</span></div>\nproduct:1\nproduct:2',
            "product:2",
        ]

        with self.assertRaises(RuntimeError):
            fetch_paged("https://example.test/list", parse_fake_products)


if __name__ == "__main__":
    unittest.main()
