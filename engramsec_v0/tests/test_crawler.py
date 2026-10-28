import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from crawler import canonical_url, crawl, feature_name, route_pattern


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        pages = {
            "/": '<html><title>Home</title><a href="/index/product.html">Products</a>'
                 '<a href="/index/product.html">Products again</a>'
                 '<a href="/index/user/index.html">User</a>'
                 '<a href="http://example.com/">Other site</a>'
                 '<a href="/logout">Log out</a>'
                 '<form method="POST" action="/checkout"><input name="payment" /></form></html>',
            "/index/product.html": '<html><title>Products</title>'
                                   '<a href="/index/product/8.html?cate=9">Item 8</a></html>',
            "/index/product/8.html?cate=9": "<html><title>Item 8</title></html>",
            "/index/user/index.html": "<html><title>User</title></html>",
        }
        body = pages.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


class CrawlerTests(unittest.TestCase):
    def test_url_normalization(self):
        self.assertEqual(
            canonical_url("/index/product.html?b=2&a=1&utm_source=x#top", "http://127.0.0.1:1234/"),
            "http://127.0.0.1:1234/index/product.html?a=1&b=2",
        )
        self.assertIsNone(canonical_url("javascript:alert(1)", "http://127.0.0.1:1234/"))

    def test_route_and_feature(self):
        u = "http://localhost:1234/index/product/8.html?cate=9"
        self.assertEqual(feature_name(u), "product")
        self.assertEqual(route_pattern(u), "/index/product/{id}.html?cate")

    def test_bfs_graph_outputs(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/"
            g = crawl(base, max_pages=4, max_depth=2, delay=0)
            m = g["metrics"]
            self.assertEqual(m["urls_visited"], 4)
            self.assertEqual(m["urls_discovered"], 4)
            self.assertGreaterEqual(m["duplicate_links_within_pages"], 1)
            self.assertEqual(m["forms_observed"], 1)
            self.assertFalse(any("logout" in n["url"] for n in g["nodes"]))
            self.assertFalse(any("example.com" in n["url"] for n in g["nodes"]))
            self.assertEqual(g["forms"][0]["submitted"], False)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
