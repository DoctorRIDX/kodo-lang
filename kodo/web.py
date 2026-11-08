"""Mode web: Kodo jadi aplikasi di browser (localhost) lewat server stdlib."""
import html
import json
import os
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .errors import KodoError, QuitSignal, NeedInput

BASE_CSS = """
:root{--bg:#f6f7fb;--fg:#1c1b22;--card:#fff;--ac:#6d4aff;--mut:#6b6b7b;--bd:#e3e3ee}
@media(prefers-color-scheme:dark){:root{--bg:#121218;--fg:#ececf3;--card:#1c1c26;--mut:#9a9ab0;--bd:#2c2c3a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,sans-serif;line-height:1.5}
#app{max-width:640px;margin:0 auto;padding:20px 16px 90px;display:flex;flex-direction:column;gap:12px}
button,input{font:inherit}
.k-title{margin:8px 0 0;font-size:1.6rem}
.k-text{margin:0;white-space:pre-wrap}
.k-button{background:var(--ac);color:#fff;border:0;border-radius:12px;padding:11px 18px;cursor:pointer;touch-action:manipulation;user-select:none}
.k-button:active{transform:scale(.97)}
.k-link{color:var(--ac)}
.k-input{display:flex;flex-direction:column;gap:4px;font-size:.9rem;color:var(--mut)}
.k-input input{padding:10px 12px;border:1px solid var(--bd);border-radius:10px;background:var(--card);color:var(--fg)}
.k-image{max-width:100%;border-radius:12px}
.k-row{display:flex;flex-direction:row;flex-wrap:wrap;gap:10px;align-items:center}
.k-column,.k-list{display:flex;flex-direction:column;gap:8px}
.k-box,.k-card{display:flex;flex-direction:column;gap:8px;background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px}
.k-divider{width:100%;border:0;border-top:1px solid var(--bd)}
.k-error{color:#e5484d;white-space:pre-wrap}
#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%) translateY(30px);background:#222;color:#fff;padding:10px 16px;border-radius:12px;opacity:0;transition:.25s;max-width:90%;white-space:pre-wrap;pointer-events:none}
#toast.on{opacity:1;transform:translateX(-50%)}
"""

JS = r"""
const app=document.getElementById('app'),toast=document.getElementById('toast');
let holdT=null,held=false;
function show(d){app.innerHTML=d.html;if(d.messages&&d.messages.length){toast.textContent=d.messages.join('\n');toast.className='on';clearTimeout(window._t);window._t=setTimeout(()=>toast.className='',3500);}}
async function send(o){try{const r=await fetch('/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});show(await r.json());}catch(e){toast.textContent='koneksi ke server Kodo putus';toast.className='on';}}
document.addEventListener('click',e=>{const el=e.target.closest('[data-click]');if(!el)return;e.preventDefault();if(held){held=false;return;}send({h:el.dataset.click});});
document.addEventListener('pointerdown',e=>{const el=e.target.closest('[data-hold]');if(!el)return;held=false;clearTimeout(holdT);holdT=setTimeout(()=>{held=true;send({h:el.dataset.hold});},650);});
['pointerup','pointerleave','pointercancel'].forEach(t=>document.addEventListener(t,()=>{clearTimeout(holdT);setTimeout(()=>{held=false},60);}));
document.addEventListener('contextmenu',e=>{if(e.target.closest('[data-hold]'))e.preventDefault();});
document.addEventListener('change',e=>{const el=e.target;if(el.dataset.prompt){send({prompt:el.dataset.prompt,v:el.value});}else if(el.dataset.h!==undefined){send({h:el.dataset.h,v:el.value});}});
"""

PAGE = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>__BASE__</style><style>__CSS__</style>__HEAD__</head>
<body><div id="app">__BODY__</div><div id="toast"></div><script>__JS__</script></body></html>"""


def esc(s):
    return html.escape(str(s), quote=True)


class WebIO(object):
    def __init__(self):
        self.messages = []
        self.answers = {}

    def print(self, s):
        self.messages.append(s)

    def prompt(self, name, label):
        if name in self.answers:
            return self.answers[name]
        raise NeedInput(name, label)


class WebApp(object):
    def __init__(self, it, io, title):
        self.it, self.io, self.title = it, io, title
        self.lock = threading.Lock()
        self.need = None
        self.pending = None
        it.start()

    def asset_url(self, src):
        if re.match(r"^(https?:|data:)", src):
            return src
        return "/asset/" + urllib.parse.quote(src)

    def prompt_html(self, name, label):
        return ('<label class="k-input k-need"><span>%s</span>'
                '<input type="text" data-prompt="%s" autofocus enterkeyhint="done"></label>') % (esc(label), esc(name))

    def nodes(self, children):
        return "".join(self.node(n) for n in children)

    def node(self, n):
        t, i = n["type"], n.get("id")
        da = ' data-id="%s"' % esc(i) if i else ""
        if t in ("column", "box", "card", "row", "list"):
            return '<div class="k-%s"%s>%s</div>' % (t, da, self.nodes(n["children"]))
        h = n.get("handlers", {})
        extra = ""
        if h.get("onclick"):
            extra += ' data-click="%s"' % h["onclick"]
        if h.get("onhold"):
            extra += ' data-hold="%s"' % h["onhold"]
        need = self.prompt_html(n["need"]["name"], n["need"]["label"]) if n.get("need") else ""
        if t == "text":
            return '<p class="k-text"%s>%s</p>%s' % (da, esc(n["text"]), need)
        if t == "title":
            return '<h2 class="k-title"%s>%s</h2>%s' % (da, esc(n["text"]), need)
        if t == "button":
            return '<button class="k-button"%s%s>%s</button>%s' % (da, extra, esc(n["text"]), need)
        if t == "link":
            return '<a class="k-link" href="#"%s%s>%s</a>' % (da, extra, esc(n["text"]))
        if t == "input":
            return ('<label class="k-input"%s><span>%s</span><input type="text" value="%s" data-h="%s"></label>'
                    % (da, esc(n["label"]), esc(n["value"]), h.get("onchange", "")))
        if t == "image":
            return '<img class="k-image"%s src="%s" alt="">' % (da, esc(self.asset_url(n["src"])))
        if t == "divider":
            return '<hr class="k-divider">'
        return ""

    def body(self):
        try:
            body = self.nodes(self.it.render()["children"])
        except NeedInput as e:
            self.need = (e.name, e.label)
            body = ""
        except KodoError as e:
            body = '<pre class="k-error">%s</pre>' % esc(e)
        if self.need:
            body = self.prompt_html(*self.need) + body
        return body

    def event(self, d):
        with self.lock:
            self.io.messages = []
            try:
                if "prompt" in d:
                    self.io.answers[d["prompt"]] = d.get("v", "")
                    self.need = None
                    if self.pending:
                        h, v = self.pending
                        self.pending = None
                        self.fire(h, v)
                elif d.get("h"):
                    self.fire(d["h"], d.get("v"))
            except QuitSignal:
                self.io.messages.append("(program memanggil quit())")
            except KodoError as e:
                self.io.messages.append("⚠ " + str(e))
            html_ = self.body()
            return {"html": html_, "messages": self.io.messages}

    def fire(self, h, v):
        try:
            self.it.fire(h, v)
        except NeedInput as e:
            self.need = (e.name, e.label)
            self.pending = (h, v)

    def page(self):
        with self.lock:
            self.io.messages = []
            body = self.body()
        head = []
        for u in self.it.urls:
            if u.endswith(".css") or "fonts.googleapis.com" in u:
                head.append('<link rel="stylesheet" href="%s">' % esc(u))
            elif u.endswith(".js"):
                head.append('<script src="%s"></script>' % esc(u))
        return (PAGE.replace("__TITLE__", esc(self.title)).replace("__BASE__", BASE_CSS)
                .replace("__CSS__", self.it.style.css()).replace("__HEAD__", "".join(head))
                .replace("__BODY__", body).replace("__JS__", JS))


def make_handler(app):
    base = os.path.realpath(app.it.base)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, data, ctype):
            if isinstance(data, str):
                data = data.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            p = urllib.parse.urlparse(self.path).path
            if p == "/":
                return self._send(200, app.page(), "text/html; charset=utf-8")
            if p.startswith("/asset/"):
                full = os.path.realpath(os.path.join(base, urllib.parse.unquote(p[7:])))
                if full.startswith(base + os.sep) and os.path.isfile(full):
                    import mimetypes
                    ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
                    with open(full, "rb") as f:
                        return self._send(200, f.read(), ctype)
            self._send(404, "tidak ditemukan", "text/plain; charset=utf-8")

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/event":
                return self._send(404, "x", "text/plain")
            n = int(self.headers.get("Content-Length") or 0)
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                d = {}
            self._send(200, json.dumps(app.event(d)), "application/json; charset=utf-8")

    return H


def serve(it, io, title, host="127.0.0.1", port=8080):
    app = WebApp(it, io, title)
    srv = ThreadingHTTPServer((host, port), make_handler(app))
    print("◆ Kodo web jalan di http://%s:%d  (Ctrl+C untuk berhenti)" % (host, port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti.")
    finally:
        srv.server_close()
