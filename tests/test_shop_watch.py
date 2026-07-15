from datetime import datetime, timezone
import unittest
from unittest import mock

from tasks import shop_watch


class ShopWatchTests(unittest.TestCase):
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
            mock.patch.object(shop_watch, "send_telegram", return_value=True),
        ):
            self.assertTrue(shop_watch.main())

        fetch.assert_called_once_with()
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
            mock.patch.object(shop_watch, "send_telegram") as send_telegram,
        ):
            self.assertTrue(shop_watch.main())

        unchanged_fetch.assert_not_called()
        cardmax_fetch.assert_called_once_with()
        send_telegram.assert_not_called()
        self.assertEqual(
            state["sites"]["cardmax"]["products"]["301"],
            {"name": "Cardmax One", "prices": [4000]},
        )
        self.assertEqual(state["sites"]["cardmax"]["revision"], 2)
        save_state.assert_called_once_with(state)


if __name__ == "__main__":
    unittest.main()
