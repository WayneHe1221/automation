import email.message
import urllib.error
import unittest
from unittest import mock

from lib.fetch import FetchError, fetch_html


class FakeResponse:
    def __init__(self, body, url="https://example.test/list"):
        self.body = body.encode("utf-8")
        self.url = url
        self.headers = email.message.Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def geturl(self):
        return self.url

    def read(self):
        return self.body


class FetchTests(unittest.TestCase):
    @mock.patch("lib.fetch.urllib.request.urlopen")
    def test_validates_required_marker(self, urlopen):
        urlopen.return_value = FakeResponse("<html>wrong page</html>")

        with self.assertRaises(FetchError):
            fetch_html("https://example.test/list", required_markers="product-card")

    @mock.patch("lib.fetch.urllib.request.urlopen")
    def test_supports_custom_user_agent(self, urlopen):
        urlopen.return_value = FakeResponse("<html>product-card</html>")

        fetch_html(
            "https://example.test/list",
            required_markers="product-card",
            user_agent="Mobile Browser",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("User-agent"), "Mobile Browser")

    @mock.patch("lib.fetch.urllib.request.urlopen")
    def test_rejects_unexpected_redirect_path(self, urlopen):
        urlopen.return_value = FakeResponse(
            "<html>product-card</html>",
            url="https://example.test/",
        )

        with self.assertRaises(FetchError):
            fetch_html(
                "https://example.test/list",
                required_markers="product-card",
                expected_path_prefix="/list",
            )

    @mock.patch("lib.fetch.time.sleep")
    @mock.patch("lib.fetch.urllib.request.urlopen")
    def test_retries_transient_network_error(self, urlopen, sleep):
        urlopen.side_effect = [
            urllib.error.URLError("temporary"),
            FakeResponse("<html>product-card</html>"),
        ]

        page = fetch_html(
            "https://example.test/list",
            required_markers="product-card",
            attempts=2,
            backoff=0,
        )

        self.assertIn("product-card", page)
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
