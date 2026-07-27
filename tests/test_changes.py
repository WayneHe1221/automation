import unittest

from lib.changes import (
    diff_products,
    has_changes,
    merge_changes,
    render_change_lines,
    summary_text,
)


def item_url(product_id):
    return f"https://example.test/{product_id}"


class DiffProductsTests(unittest.TestCase):
    def test_detects_added_removed_and_price(self):
        previous = {
            "1": {"name": "Stay", "qty": 5},
            "2": "Gone",
            "3": {"name": "Priced", "prices": [4000]},
        }
        current = {
            "1": {"name": "Stay", "qty": 2},
            "3": {"name": "Priced", "prices": [3800]},
            "4": {"name": "Fresh", "qty": 7},
        }

        changes = diff_products(previous, current)

        self.assertEqual(changes["added"], [{"id": "4", "name": "Fresh", "qty": 7}])
        self.assertEqual(changes["removed"], [{"id": "2", "name": "Gone"}])
        self.assertEqual(
            changes["price"], [{"id": "3", "name": "Priced", "old": [4000], "new": [3800]}]
        )

    def test_qty_change_alone_is_not_a_change(self):
        previous = {"1": {"name": "Stay", "qty": 5}}
        current = {"1": {"name": "Stay", "qty": 40}}

        self.assertFalse(has_changes(diff_products(previous, current)))

    def test_unknown_price_on_either_side_is_not_a_change(self):
        previous = {"1": "Plain", "2": {"name": "Known", "prices": [1000]}}
        current = {"1": {"name": "Plain", "prices": [1200]}, "2": "Known"}

        self.assertFalse(has_changes(diff_products(previous, current)))

    def test_identical_lists_have_no_changes(self):
        products = {"1": {"name": "Same", "qty": 1}, "2": "Same too"}

        self.assertFalse(has_changes(diff_products(products, products)))


class RenderChangeLinesTests(unittest.TestCase):
    def test_no_changes_render_no_lines(self):
        self.assertEqual(
            render_change_lines(diff_products({"1": "A"}, {"1": "A"}), item_url), []
        )

    def test_removed_items_carry_no_link_and_others_do(self):
        changes = diff_products(
            {"1": {"name": "Dropped"}, "2": {"name": "Kept", "qty": 9}},
            {"2": {"name": "Kept", "qty": 4}, "3": {"name": "New & <fresh>"}},
        )

        text = "\n".join(render_change_lines(changes, item_url))

        self.assertEqual(summary_text(changes), "新增 1・下架 1")
        self.assertIn("• <b>New &amp; &lt;fresh&gt;</b>\n  https://example.test/3", text)
        self.assertIn("• Dropped", text)
        self.assertNotIn("https://example.test/1", text)
        self.assertNotIn("在庫 9", text)  # 在庫變化不通知

    def test_price_change_is_formatted_with_yen(self):
        changes = diff_products(
            {"1": {"name": "Deck", "prices": [12000]}},
            {"1": {"name": "Deck", "prices": [9800]}},
        )

        text = "\n".join(render_change_lines(changes, item_url))

        self.assertIn("• <b>Deck</b> 12,000円 → 9,800円", text)

    def test_long_section_is_truncated_with_total(self):
        current = {str(i): {"name": f"Item {i}"} for i in range(30)}

        text = "\n".join(
            render_change_lines(diff_products({}, current), item_url, max_items=5)
        )

        self.assertEqual(text.count("• <b>"), 5)
        self.assertIn("…等共 30 件", text)


class MergeChangesTests(unittest.TestCase):
    def test_counts_across_sources(self):
        first = diff_products({"1": "Gone"}, {"2": {"name": "New"}})
        second = diff_products({}, {"3": {"name": "Also new"}})

        merged = merge_changes([first, second])

        self.assertEqual(summary_text(merged), "新增 2・下架 1")


if __name__ == "__main__":
    unittest.main()
