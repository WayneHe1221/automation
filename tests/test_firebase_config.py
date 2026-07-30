import json
import unittest
from pathlib import Path


AUTH_DOMAIN = "card-shop-tracker.web.app"  # FIREBASE_AUTH_DOMAIN variable


def hosting_header(name):
    config = json.loads(Path("firebase.json").read_text())
    headers = config["hosting"]["headers"][0]["headers"]
    return next(header["value"] for header in headers if header["key"] == name)


class FirebaseConfigTests(unittest.TestCase):
    def test_hosting_target_covers_primary_and_auth_domain_sites(self):
        """部署目標必須包含主要網址，以及仍作為 authDomain 的舊網址。"""
        hosting = json.loads(Path("firebase.json").read_text())["hosting"]
        firebaserc = json.loads(Path(".firebaserc").read_text())
        project = firebaserc["projects"]["default"]
        sites = firebaserc["targets"][project]["hosting"][hosting["target"]]

        self.assertIn("cardradar", sites)
        self.assertIn(AUTH_DOMAIN.removesuffix(".web.app"), sites)

    def test_content_security_policy_allows_the_auth_domain_iframe(self):
        """儀表板網域與 authDomain 不同，Firebase 登入的 iframe 必須明確放行。"""
        content_security_policy = hosting_header("Content-Security-Policy")

        frame_src = next(
            directive
            for directive in content_security_policy.split(";")
            if directive.strip().startswith("frame-src")
        )
        self.assertIn(f"https://{AUTH_DOMAIN}", frame_src)

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
