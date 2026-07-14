import unittest

from lib.notify import split_telegram_html


class NotifyTests(unittest.TestCase):
    def test_splits_only_between_complete_lines(self):
        message = "".join(f"<b>Item {index}</b>\n" for index in range(30))
        chunks = split_telegram_html(message, limit=80)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 80 for chunk in chunks))
        self.assertEqual(sum(chunk.count("<b>") for chunk in chunks), 30)
        self.assertEqual(sum(chunk.count("</b>") for chunk in chunks), 30)

    def test_long_line_falls_back_to_escaped_plain_text(self):
        chunks = split_telegram_html("<b>" + "x" * 30 + "</b>", limit=10)

        self.assertTrue(all(len(chunk) <= 10 for chunk in chunks))
        self.assertNotIn("<b>", "".join(chunks))


if __name__ == "__main__":
    unittest.main()
