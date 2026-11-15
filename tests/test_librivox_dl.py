import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import librivox_dl as lv

PRIDE = {
    "id": "253",
    "title": "Pride and Prejudice",
    "authors": [{"id": "155", "first_name": "Jane", "last_name": "Austen",
                 "dob": "1776", "dod": "1817"}],
    "url_librivox": "https://librivox.org/pride-and-prejudice-by-jane-austen/",
    "url_zip_file": "https://archive.org/compress/example.zip",
    "totaltimesecs": "47204",
    "language": "English",
}

ANON = {
    "id": "99",
    "title": "Anonymous Work",
    "authors": [],
    "url_librivox": "https://librivox.org/anon/",
    "url_zip_file": None,
    "totaltimesecs": None,
    "language": "English",
}


class FakeResponse:
    def __init__(self, payload: bytes, length=None):
        self._buf = io.BytesIO(payload)
        self.headers = {"Content-Length": str(length or len(payload))}

    def read(self, n=-1):
        return self._buf.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def json_response(obj) -> FakeResponse:
    return FakeResponse(json.dumps(obj).encode("utf-8"))


class TestHelpers(unittest.TestCase):
    def test_author_names(self):
        self.assertEqual(lv.author_names(PRIDE), "Jane Austen")
        self.assertEqual(lv.author_names(ANON), "Unknown author")

    def test_format_duration(self):
        self.assertEqual(lv.format_duration("47204"), "13h 07m")
        self.assertEqual(lv.format_duration("600"), "10m")
        self.assertEqual(lv.format_duration(None), "unknown length")

    def test_slugify(self):
        self.assertEqual(lv.slugify("Pride & Prejudice!"), "pride-prejudice")
        self.assertEqual(lv.slugify("   "), "audiobook")


class TestApi(unittest.TestCase):
    def test_search_builds_query(self):
        with mock.patch.object(lv, "_open",
                               return_value=json_response({"books": [PRIDE]})) as m:
            books = lv.search_books(title="pride", author="austen")
        self.assertEqual(books[0]["id"], "253")
        url = m.call_args[0][0]
        self.assertIn("title=pride", url)
        self.assertIn("author=austen", url)
        self.assertIn("format=json", url)

    def test_search_requires_a_term(self):
        with self.assertRaises(lv.LibriVoxError):
            lv.search_books()

    def test_search_limit_clamped(self):
        with mock.patch.object(lv, "_open",
                               return_value=json_response({"books": []})) as m:
            lv.search_books(title="x", limit=999)
        self.assertIn("limit=50", m.call_args[0][0])

    def test_get_book_missing(self):
        with mock.patch.object(lv, "_open",
                               return_value=json_response({"books": []})):
            with self.assertRaises(lv.LibriVoxError):
                lv.get_book("99999999")

    def test_network_error_wrapped(self):
        import urllib.error
        with mock.patch.object(lv, "_open",
                               side_effect=urllib.error.URLError("boom")):
            with self.assertRaises(lv.LibriVoxError):
                lv.search_books(title="x")

    def test_describe(self):
        text = lv.describe(PRIDE)
        self.assertIn("[253] Pride and Prejudice", text)
        self.assertIn("Jane Austen", text)
        self.assertIn("13h 07m", text)


class TestDownload(unittest.TestCase):
    def test_download_saves_file(self):
        payload = b"fake-zip-bytes" * 100
        responses = [json_response({"books": [PRIDE]}), FakeResponse(payload)]
        with mock.patch.object(lv, "_open", side_effect=responses):
            with tempfile.TemporaryDirectory() as tmp:
                dest = lv.download_book("253", output_dir=tmp, progress=False)
                self.assertTrue(os.path.basename(dest).startswith(
                    "pride-and-prejudice-253"))
                with open(dest, "rb") as fh:
                    self.assertEqual(fh.read(), payload)

    def test_download_without_zip(self):
        with mock.patch.object(lv, "_open",
                               return_value=json_response({"books": [ANON]})):
            with self.assertRaises(lv.LibriVoxError) as ctx:
                lv.download_book("99", progress=False)
        self.assertIn("no downloadable zip", str(ctx.exception))


class TestCli(unittest.TestCase):
    def test_search_cli_no_results(self):
        from io import StringIO
        buf = StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            with mock.patch.object(lv, "_open",
                                   return_value=json_response({"books": []})):
                rc = lv.main(["search", "zzzz-not-a-book"])
        finally:
            sys.stdout = old
        self.assertEqual(rc, 0)
        self.assertIn("No results", buf.getvalue())

    def test_error_exit_code(self):
        from io import StringIO
        err = StringIO()
        old = sys.stderr
        sys.stderr = err
        try:
            with mock.patch.object(lv, "_open",
                                   return_value=json_response({"books": []})):
                rc = lv.main(["info", "1"])
        finally:
            sys.stderr = old
        self.assertEqual(rc, 1)
        self.assertIn("no LibriVox book", err.getvalue())


if __name__ == "__main__":
    unittest.main()
