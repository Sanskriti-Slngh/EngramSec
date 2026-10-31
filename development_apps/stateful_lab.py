"""Disposable SQLite browser lab; its ground truth is operator-only."""
from __future__ import annotations
import json
import sqlite3
import threading
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def start_stateful_lab(database: Path):
    log = []
    snapshot = database.with_suffix('.snapshot.sqlite')
    with closing(sqlite3.connect(snapshot)) as con:
        con.executescript('DROP TABLE IF EXISTS records; CREATE TABLE records (id INTEGER PRIMARY KEY, name TEXT); INSERT INTO records VALUES (1, "Alpha"), (2, "Beta");')
        con.commit()
    def db():
        return sqlite3.connect(database)
    def reset():
        with closing(sqlite3.connect(snapshot)) as source, closing(db()) as target:
            source.backup(target)
        log.clear()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def send(self, data, status=200, content_type='text/html', headers=()):
            body = data.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            for key, value in headers:
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            path = urlsplit(self.path).path
            log.append(('GET', path))
            if path == '/':
                with db() as con:
                    records = con.execute('SELECT id,name FROM records ORDER BY id').fetchall()
                links = ''.join(f'<a href="/records/{i}">{name}</a> ' for i, name in records)
                self.send(f'''<!doctype html><title>Records</title><h1>Records</h1>{links}
                <form id="create"><label>Title <input name="title" value="Example"></label><button>Create record</button></form>
                <form id="search"><label>Query <input name="query" value="Alpha"></label><button>Submit</button></form>
                <a href="/counter">Counter</a><button id="delete">Delete all records</button>
                <script>
                document.querySelector('#create').onsubmit = async e => {{e.preventDefault(); let r=await fetch('/api/records',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{name:'New record'}})}}); let x=await r.json(); location.href='/records/'+x.id;}};
                document.querySelector('#search').onsubmit = async e => {{e.preventDefault(); let r=await fetch('/api/search',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{q:'Alpha'}})}}); document.querySelector('#out').textContent=await r.text();}};
                document.querySelector('#delete').onclick=()=>fetch('/api/delete',{{method:'POST'}});
                </script><div id="out"></div>''')
            elif path.startswith('/records/') and path.rsplit('/', 1)[-1].isdigit():
                ident = int(path.rsplit('/', 1)[-1])
                with db() as con:
                    row = con.execute('SELECT name FROM records WHERE id=?', (ident,)).fetchone()
                if row is None:
                    self.send('missing', 404); return
                self.send(f'''<title>Record</title><h1>{row[0]}</h1><a href="/">All records</a>
                <form id="update"><label>New name <input name="name" value="Changed"></label><button>Submit</button></form>
                <script>document.querySelector('#update').onsubmit=async e=>{{e.preventDefault();await fetch('/api/records/{ident}',{{method:'POST'}});location.reload()}}</script>''')
            elif path == '/counter':
                with db() as con:
                    con.execute('INSERT INTO records(name) VALUES (?)', ('GET mutation',))
                self.send('', 302, headers=(('Location', '/'),))
            else:
                self.send('missing', 404)
        def do_POST(self):
            path = urlsplit(self.path).path
            log.append(('POST', path))
            length = int(self.headers.get('Content-Length', 0))
            self.rfile.read(length)
            if path == '/api/records':
                with db() as con:
                    ident = con.execute('INSERT INTO records(name) VALUES (?)', ('New record',)).lastrowid
                self.send(json.dumps({'id': ident}), content_type='application/json')
            elif path == '/api/search':
                self.send(json.dumps(['Alpha']), content_type='application/json')
            elif path.startswith('/api/records/') and path.rsplit('/', 1)[-1].isdigit():
                with db() as con:
                    con.execute('UPDATE records SET name=? WHERE id=?', ('Changed', int(path.rsplit('/', 1)[-1])))
                self.send('{"ok":true}', content_type='application/json')
            elif path == '/api/delete':
                with db() as con:
                    con.execute('DELETE FROM records')
                self.send('{"ok":true}', content_type='application/json')
            else:
                self.send('missing', 404)
    reset()
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f'http://127.0.0.1:{server.server_port}/', reset, log
