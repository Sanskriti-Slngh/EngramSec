from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


PAGE = """<!doctype html><html><head><title>{title}</title></head><body>
<header><a href="/">Northstar Shop</a><a href="/cart">Cart</a></header>
<main>{body}</main>{script}</body></html>"""


class ShopHandler(BaseHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        return

    def _send(self, body: str, status: int = 200, *, content_type: str = "text/html", cookie: str | None = None) -> None:
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def _page(self, title: str, body: str, script: str = "") -> None:
        self._send(PAGE.format(title=title, body=body, script=script))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path == "/":
            self._page(
                "Northstar Shop",
                """<h1>Northstar Shop</h1>
<a href="/products/101">Trail lantern</a><a href="/products/202">Camp kettle</a>
<button aria-controls="categories" id="categories-button">Browse categories</button>
<section id="categories" hidden><a href="/category/outdoors">Outdoor collection</a></section>
<div role="tab" tabindex="0" id="deals-tab">Current deals</div>
<section id="deals" hidden><a href="/deals">See all deals</a></section>
<details><summary>Shipping and returns</summary><a href="/returns">Returns guide</a></details>
<form method="post" action="/admin"><label>Password <input type="password" name="password"></label><button>Admin login</button></form>
""",
                """<script>
document.querySelector('#categories-button').onclick=()=>document.querySelector('#categories').hidden=false;
document.querySelector('#deals-tab').onclick=()=>document.querySelector('#deals').hidden=false;
</script>""",
            )
            return
        if parsed.path in {"/products/101", "/products/202"}:
            sku = parsed.path.rsplit("/", 1)[-1]
            name = "Trail lantern" if sku == "101" else "Camp kettle"
            self._page(
                name,
                f"""<h1>{name}</h1><p data-sku="{sku}">SKU {sku}</p>
<button id="reviews">Load customer reviews</button>
<form method="post" action="/cart/items"><input type="hidden" name="sku" value="{sku}"><button>Add sample to cart</button></form>
<section id="reviews-list"></section>""",
                f"""<script>document.querySelector('#reviews').onclick=async()=>{{
const r=await fetch('/api/reviews?product={sku}&limit=5');
document.querySelector('#reviews-list').textContent=(await r.json()).summary;
}};</script>""",
            )
            return
        if parsed.path == "/category/outdoors":
            self._page("Outdoor collection", "<h1>Outdoor collection</h1><a href='/products/101'>Featured lantern</a>")
            return
        if parsed.path == "/deals":
            self._page("Deals", "<h1>Current deals</h1><p>Bundle savings</p>")
            return
        if parsed.path == "/returns":
            self._page("Returns", "<h1>Returns guide</h1><p>Thirty day returns</p>")
            return
        if parsed.path == "/cart":
            ready = "shop_cart=ready" in (self.headers.get("Cookie") or "")
            body = "<h1>Your cart</h1><a href='/checkout'>Begin checkout</a>" if ready else "<h1>Your cart is empty</h1>"
            self._page("Cart", body)
            return
        if parsed.path == "/checkout":
            self._page("Checkout", "<h1>Checkout details</h1><p>Disposable test checkout</p>")
            return
        if parsed.path == "/api/reviews":
            product = parse_qs(parsed.query).get("product", [""])[0]
            self._send(json.dumps({"summary": f"Reviews loaded for {product}"}), content_type="application/json")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode(errors="replace")
        if self.path == "/cart/items" and parse_qs(body).get("sku"):
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/cart")
            self.send_header("Set-Cookie", "shop_cart=ready; Path=/; HttpOnly; SameSite=Lax")
            self.end_headers()
            return
        self.send_error(HTTPStatus.FORBIDDEN)


def start_heldout_shop() -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), ShopHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/"
