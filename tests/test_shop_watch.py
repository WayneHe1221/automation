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


if __name__ == "__main__":
    unittest.main()
