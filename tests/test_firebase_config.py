import json
import unittest
from pathlib import Path


def hosting_header(name):
    config = json.loads(Path("firebase.json").read_text())
    headers = config["hosting"]["headers"][0]["headers"]
    return next(header["value"] for header in headers if header["key"] == name)


class FirebaseConfigTests(unittest.TestCase):
    def test_referrer_policy_supports_restricted_browser_api_key(self):
        referrer_policy = hosting_header("Referrer-Policy")

        self.assertEqual("strict-origin-when-cross-origin", referrer_policy)

    def test_content_security_policy_allows_firebase_auth_helpers(self):
        content_security_policy = hosting_header("Content-Security-Policy")

        self.assertIn("script-src 'self' https://apis.google.com", content_security_policy)
        self.assertIn("frame-src 'self'", content_security_policy)

    def test_html_shell_is_not_cached(self):
        cache_control = hosting_header("Cache-Control")

        self.assertEqual("no-cache, no-store, must-revalidate", cache_control)


if __name__ == "__main__":
    unittest.main()
