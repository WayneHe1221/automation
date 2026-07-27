from datetime import datetime, timezone
import unittest
from unittest import mock

from lib import digest
from tasks import shop_watch


class ShopWatchTests(unittest.TestCase):
    def setUp(self):
        digest.reset()
        self.addCleanup(digest.reset)

    def test_missing_source_initializes_even_if_today_already_ran(self):
        fetch = mock.Mock(return_value={})
        state = {
            "last_run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "sites": {},
        }
        site = {
            "key": "new_deck",
            "label": "New Deck Source",
            "fetch": fetch,
            "item_url": lambda product_id: f"https://example.test/{product_id}",
            "allow_empty": True,
        }

        with (
            mock.patch.object(shop_watch, "SITES", [site]),
            mock.patch.object(shop_watch, "load_state", return_value=state),
            mock.patch.object(shop_watch, "save_state") as save_state,
        ):
            self.assertTrue(shop_watch.main())

        fetch.assert_called_once_with()
        self.assertEqual(digest.pending_labels(), [])
        self.assertEqual(state["sites"]["new_deck"]["products"], {})
        save_state.assert_called_once_with(state)

    def test_changed_revision_refreshes_only_that_source_and_saves_prices(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        unchanged_fetch = mock.Mock()
        cardmax_fetch = mock.Mock(
            return_value={
                "301": {
                    "name": "Cardmax One",
                    "in_stock": True,
                    "prices": [4000],
                }
            }
        )
        state = {
            "last_run_date": today,
            "sites": {
                "unchanged": {"products": {"1": "Existing"}},
                "cardmax": {
                    "products": {"301": "Cardmax One"},
                    "revision": 1,
                },
            },
        }
        sites = [
            {
                "key": "unchanged",
                "label": "Unchanged",
                "fetch": unchanged_fetch,
                "item_url": lambda product_id: f"https://example.test/{product_id}",
            },
            {
                "key": "cardmax",
                "label": "Cardmax",
                "revision": 2,
                "require_prices": True,
                "fetch": cardmax_fetch,
                "item_url": lambda product_id: f"https://example.test/{product_id}",
            },
        ]

        with (
            mock.patch.object(shop_watch, "SITES", sites),
            mock.patch.object(shop_watch, "load_state", return_value=state),
            mock.patch.object(shop_watch, "save_state") as save_state,
        ):
            self.assertTrue(shop_watch.main())

        unchanged_fetch.assert_not_called()
        cardmax_fetch.assert_called_once_with()
        self.assertEqual(digest.pending_labels(), [])
        self.assertEqual(
            state["sites"]["cardmax"]["products"]["301"],
            {"name": "Cardmax One", "prices": [4000]},
        )
        self.assertEqual(state["sites"]["cardmax"]["revision"], 2)
        save_state.assert_called_once_with(state)

    def _changed_site_state(self):
        fetch = mock.Mock(
            return_value={
                "1": {"name": "Kept", "in_stock": True},
                "9": {"name": "Fresh", "in_stock": True},
            }
        )
        state = {
            "last_run_date": "2000-01-01",
            "sites": {
                "shop": {"products": {"1": "Kept", "2": "Gone"}, "raw_count": 2},
            },
        }
        site = {
            "key": "shop",
            "label": "Shop",
            "fetch": fetch,
            "item_url": lambda product_id: f"https://example.test/{product_id}",
        }
        return site, state

    def test_changed_source_commits_baseline_only_after_digest_is_sent(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        site, state = self._changed_site_state()

        with (
            mock.patch.object(shop_watch, "SITES", [site]),
            mock.patch.object(shop_watch, "load_state", return_value=state),
            mock.patch.object(shop_watch, "save_state"),
            mock.patch.object(digest, "send_telegram", return_value=True) as send_telegram,
        ):
            self.assertTrue(shop_watch.main())
            # 通知還沒送出：基準與執行日都不能先前進。
            self.assertEqual(digest.pending_labels(), ["Shop"])
            self.assertEqual(state["sites"]["shop"]["products"], {"1": "Kept", "2": "Gone"})
            self.assertEqual(state["last_run_date"], "2000-01-01")

            self.assertTrue(digest.flush())

        send_telegram.assert_called_once()
        self.assertIn("1 個來源・新增 1・下架 1", send_telegram.call_args.args[0])
        self.assertEqual(state["sites"]["shop"]["products"], {"1": "Kept", "9": "Fresh"})
        self.assertEqual(state["last_run_date"], today)

    def test_failed_digest_keeps_baseline_for_retry(self):
        site, state = self._changed_site_state()

        with (
            mock.patch.object(shop_watch, "SITES", [site]),
            mock.patch.object(shop_watch, "load_state", return_value=state),
            mock.patch.object(shop_watch, "save_state"),
            mock.patch.object(digest, "send_telegram", return_value=False),
        ):
            self.assertTrue(shop_watch.main())
            self.assertFalse(digest.flush())

        self.assertEqual(state["sites"]["shop"]["products"], {"1": "Kept", "2": "Gone"})
        self.assertEqual(state["last_run_date"], "2000-01-01")


if __name__ == "__main__":
    unittest.main()
