import unittest
from unittest import mock

from lib import digest
from lib.changes import diff_products


def item_url(product_id):
    return f"https://example.test/{product_id}"


class DigestTests(unittest.TestCase):
    def setUp(self):
        digest.reset()
        self.addCleanup(digest.reset)

    def test_no_changes_are_not_registered_and_flush_sends_nothing(self):
        registered = digest.add(
            "Shop", diff_products({"1": "A"}, {"1": "A"}), item_url, mock.Mock()
        )

        with mock.patch.object(digest, "send_telegram") as send_telegram:
            self.assertTrue(digest.flush())

        self.assertFalse(registered)
        send_telegram.assert_not_called()

    def test_all_sources_share_one_message_and_commit_after_success(self):
        first_commit, second_commit = mock.Mock(), mock.Mock()
        digest.add("Shop A", diff_products({}, {"1": {"name": "New A"}}), item_url, first_commit)
        digest.add("Shop B", diff_products({"2": {"name": "Old B"}}, {}), item_url, second_commit)

        with mock.patch.object(digest, "send_telegram", return_value=True) as send_telegram:
            self.assertTrue(digest.flush())

        send_telegram.assert_called_once()
        message = send_telegram.call_args.args[0]
        self.assertIn("🔔 <b>商品異動</b>", message)
        self.assertIn("2 個來源・新增 1・下架 1", message)
        self.assertIn("▍<b>Shop A</b>", message)
        self.assertIn("▍<b>Shop B</b>", message)
        first_commit.assert_called_once_with()
        second_commit.assert_called_once_with()
        self.assertEqual(digest.pending_labels(), [])

    def test_failed_send_keeps_pending_and_skips_commit(self):
        commit = mock.Mock()
        digest.add("Shop", diff_products({}, {"1": {"name": "New"}}), item_url, commit)

        with mock.patch.object(digest, "send_telegram", return_value=False):
            self.assertFalse(digest.flush())

        commit.assert_not_called()
        self.assertEqual(digest.pending_labels(), ["Shop"])


if __name__ == "__main__":
    unittest.main()
