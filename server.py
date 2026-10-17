"""Local web interface for the library manager. Run with ``python server.py``."""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from library import Library


HOST, PORT = "127.0.0.1", 8000


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query).get("q", [""])[0]
        library = Library()
        try:
            books = library.books(query)
            members = library.members()
            loans = library.active_loans()
            book_rows = "".join(
                f"<tr><td>{b['id']}</td><td>{esc(b['title'])}</td><td>{esc(b['author'])}</td>"
                f"<td>{esc(b['isbn'] or '—')}</td><td>{b['available']} / {b['copies']}</td></tr>"
                for b in books
            ) or '<tr><td colspan="5" class="empty">No books found.</td></tr>'
            member_options = "".join(
                f'<option value="{m["id"]}">{esc(m["name"])} (#{m["id"]})</option>' for m in members
            )
            book_options = "".join(
                f'<option value="{b["id"]}">{esc(b["title"])} ({b["available"]} available)</option>'
                for b in library.books() if b["available"] > 0
            )
            loan_rows = "".join(
                f'<tr><td>{l["id"]}</td><td>{esc(l["title"])}</td><td>{esc(l["name"])}</td>'
                f'<td>{esc(l["borrowed_on"])}</td><td><form method="post"><input type="hidden" name="action" value="return">'
                f'<input type="hidden" name="loan_id" value="{l["id"]}"><button>Return</button></form></td></tr>'
                for l in loans
            ) or '<tr><td colspan="5" class="empty">No active loans.</td></tr>'
        finally:
            library.close()

        message = parse_qs(parsed.query).get("message", [""])[0]
        page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Library Manager</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f4f6fb;color:#172033;font:15px/1.5 system-ui, sans-serif}}header{{background:#172554;color:white;padding:28px max(24px,calc((100% - 1100px)/2))}}header h1{{margin:0;font-size:26px}}header p{{margin:4px 0 0;color:#c7d2fe}}main{{max-width:1100px;margin:24px auto;padding:0 20px;display:grid;gap:18px;grid-template-columns:1fr 1fr}}section{{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:20px;box-shadow:0 2px 8px #0f172a0a}}section.wide{{grid-column:1/-1}}h2{{font-size:18px;margin:0 0 14px}}form.stack{{display:grid;gap:10px}}input,select{{width:100%;padding:10px 12px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}}button{{border:0;border-radius:7px;background:#2563eb;color:white;padding:10px 14px;font:600 14px system-ui;cursor:pointer}}button:hover{{background:#1d4ed8}}table{{width:100%;border-collapse:collapse;text-align:left}}th,td{{padding:10px 8px;border-bottom:1px solid #e2e8f0;vertical-align:middle}}th{{color:#475569;font-size:13px}}td form{{margin:0}}.empty{{color:#64748b;text-align:center;padding:22px}}.notice{{max-width:1100px;margin:18px auto 0;padding:12px 18px;background:#dcfce7;border-radius:8px;color:#166534}}.search{{display:flex;gap:8px;margin-bottom:12px}}.search input{{flex:1}}@media(max-width:720px){{main{{grid-template-columns:1fr}}section.wide{{grid-column:auto}}table{{font-size:13px}}}}
</style></head><body><header><h1>Library Manager</h1><p>Manage your catalog, members, and active loans</p></header>
{f'<div class="notice">{esc(message)}</div>' if message else ''}<main>
<section class="wide"><h2>Book catalog</h2><form class="search" method="get"><input name="q" placeholder="Search title, author, or ISBN" value="{esc(query)}"><button>Search</button></form><table><thead><tr><th>ID</th><th>Title</th><th>Author</th><th>ISBN</th><th>Available</th></tr></thead><tbody>{book_rows}</tbody></table></section>
<section><h2>Add a book</h2><form class="stack" method="post"><input type="hidden" name="action" value="add_book"><input name="title" placeholder="Title" required><input name="author" placeholder="Author" required><input name="isbn" placeholder="ISBN (optional)"><input name="copies" type="number" min="1" value="1" required><button>Add book</button></form></section>
<section><h2>Add a member</h2><form class="stack" method="post"><input type="hidden" name="action" value="add_member"><input name="name" placeholder="Member name" required><input name="email" type="email" placeholder="Email (optional)"><button>Add member</button></form><h2 style="margin-top:20px">Borrow a book</h2><form class="stack" method="post"><input type="hidden" name="action" value="borrow"><select name="book_id" required><option value="">Choose available book</option>{book_options}</select><select name="member_id" required><option value="">Choose member</option>{member_options}</select><button>Record loan</button></form></section>
<section class="wide"><h2>Active loans</h2><table><thead><tr><th>Loan</th><th>Book</th><th>Member</th><th>Borrowed</th><th></th></tr></thead><tbody>{loan_rows}</tbody></table></section>
</main></body></html>'''
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        params = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode())
        get = lambda key, default="": params.get(key, [default])[0]
        library = Library()
        try:
            action = get("action")
            if action == "add_book":
                library.add_book(get("title"), get("author"), get("isbn") or None, int(get("copies", "1")))
                message = "Book added."
            elif action == "add_member":
                library.add_member(get("name"), get("email") or None)
                message = "Member added."
            elif action == "borrow":
                library.borrow(int(get("book_id")), int(get("member_id")))
                message = "Loan recorded."
            elif action == "return":
                library.return_book(int(get("loan_id")))
                message = "Book returned."
            else:
                raise ValueError("Unknown action.")
        except (ValueError, Exception) as exc:
            message = f"Error: {exc}"
        finally:
            library.close()
        self.send_response(303)
        self.send_header("Location", "/?" + urlencode({"message": message}))
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Library Manager running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
