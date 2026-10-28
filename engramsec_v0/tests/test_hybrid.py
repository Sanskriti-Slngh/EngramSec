import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from crawler import crawl
from hybrid import crawl_hybrid


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/user":
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return
        pages = {
            "/": '<html><title>Home</title><a href="/user">User</a>'
                 '<a href="/about">About</a><a href="/about">Repeat</a></html>',
            "/about": '<html><title>About</title><a href="/more">More</a></html>',
            "/more": '<html><title>More</title></html>',
            "/login": '<html><title>Login</title><form method="post" action="/auth">'
                      '<input name="username"><input name="password" type="password">'
                      '</form><a href="/register">Register</a></html>',
            "/register": '<html><title>Register</title></html>',
        }
        body = pages.get(self.path)
        if body is None:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


class HybridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_redirect_probe_reaches_login_earlier_than_bfs(self):
        bfs = crawl(self.url, max_pages=4, max_depth=2, delay=0)
        hybrid = crawl_hybrid(self.url, max_pages=4, max_depth=2, delay=0)
        a = [x["url"].split(f":{self.server.server_port}")[-1] for x in bfs["trace"]]
        b = [x["url"].split(f":{self.server.server_port}")[-1] for x in hybrid["trace"]]
        self.assertEqual(a, ["/", "/user", "/about", "/login"])
        self.assertEqual(b, ["/", "/user", "/login", "/register"])
        self.assertEqual(hybrid["metrics"]["distinct_form_signatures"], 1)
        self.assertEqual(hybrid["metrics"]["requests_sent"], 4)

    def test_no_probe_mode_matches_bfs_order_except_redirect(self):
        # Direct redirects are always followed immediately even if probes are disabled.
        graph = crawl_hybrid(self.url, max_pages=5, max_depth=2, delay=0, probe_hops=0)
        self.assertEqual(graph["trace"][2]["url"].split("/")[-1], "login")

    def test_no_probe_no_priority_matches_bfs_order(self):
        bfs = crawl(self.url, max_pages=5, max_depth=2, delay=0)
        variant = crawl_hybrid(self.url, max_pages=5, max_depth=2,
                               delay=0, probe_hops=0, immediate_redirect=False)
        self.assertEqual([x["url"] for x in bfs["trace"]],
                         [x["url"] for x in variant["trace"]])

    def test_depth_zero_only_root(self):
        graph = crawl_hybrid(self.url, max_pages=40, max_depth=0, delay=0)
        self.assertEqual(graph["metrics"]["requests_sent"], 1)
        self.assertEqual(graph["metrics"]["max_depth_visited"], 0)

    def test_localhost_guard(self):
        with self.assertRaises(ValueError):
            crawl_hybrid("https://example.com/", delay=0)


if __name__ == "__main__":
    unittest.main()
