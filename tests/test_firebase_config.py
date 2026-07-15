import json
import unittest
from pathlib import Path


class FirebaseConfigTests(unittest.TestCase):
    def test_referrer_policy_supports_restricted_browser_api_key(self):
        config = json.loads(Path("firebase.json").read_text())
        headers = config["hosting"]["headers"][0]["headers"]
        referrer_policy = next(
            header["value"] for header in headers if header["key"] == "Referrer-Policy"
        )

        self.assertEqual("strict-origin-when-cross-origin", referrer_policy)


if __name__ == "__main__":
    unittest.main()
