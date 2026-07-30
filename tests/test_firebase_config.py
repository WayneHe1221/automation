import json
import unittest
from pathlib import Path


AUTH_DOMAIN = "card-shop-tracker.web.app"  # FIREBASE_AUTH_DOMAIN variable
PRIMARY_SITE = "cardradar"


def hosting_sites():
    return json.loads(Path("firebase.json").read_text())["hosting"]


def hosting_header(name):
    site = next(site for site in hosting_sites() if site["site"] == PRIMARY_SITE)
    headers = site["headers"][0]["headers"]
    return next(header["value"] for header in headers if header["key"] == name)


class FirebaseConfigTests(unittest.TestCase):
    def test_deploy_covers_primary_and_auth_domain_sites(self):
        """主要網址與仍作為 authDomain 的舊網址都要部署，舊網址不能只留舊版本。"""
        self.assertEqual(
            [PRIMARY_SITE, AUTH_DOMAIN.removesuffix(".web.app")],
            [site["site"] for site in hosting_sites()],
        )

    def test_all_hosting_sites_share_the_same_configuration(self):
        """兩個網址必須提供完全相同的內容與安全標頭，只有 site 名稱不同。"""
        without_site = [
            {key: value for key, value in site.items() if key != "site"}
            for site in hosting_sites()
        ]

        self.assertTrue(all(entry == without_site[0] for entry in without_site))

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
