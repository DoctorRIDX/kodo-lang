"""CLI Kodo: kodo run | serve | check | new | repl | version"""
import argparse
import os
import sys

from . import __version__
from .errors import KodoError, QuitSignal
from .interp import Interpreter
from .lexer import brace_delta
from .parser import parse_program

SCAFFOLD = '''// {name} - dibuat dengan Kodo
state count = 0

void tambah() {{
   count = count + 1
}}

void.screen main {{
   title ; judul."{name}"
   text ; info."Hitungan : {{count}}"
   button ; plus."Tambah".onclick.active.tambah()
}}

void.screen style {{
   judul ; {{
      color ; #6d4aff
      set.size ; 28px
   }}
}}
'''


def read_file(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print("Tidak bisa membuka %s: %s" % (path, e.strerror), file=sys.stderr)
        sys.exit(2)


def load(path, io):
    it = Interpreter(io, base_dir=os.path.dirname(os.path.abspath(path)), file=os.path.basename(path))
    it.load_source(read_file(path))
    return it


def cmd_run(a):
    if a.web:
        return cmd_serve(a)
    from .term import TermIO, run_ui
    it = load(a.file, TermIO())
    if it.screens:
        return run_ui(it)
    if "main" in it.funcs:
        it.call("main", [])
    return 0


def cmd_serve(a):
    from .web import WebIO, serve
    io = WebIO()
    it = load(a.file, io)
    if not it.screens:
        print("File ini tidak punya void.screen, tidak ada yang bisa ditampilkan di web.", file=sys.stderr)
        return 1
    serve(it, io, os.path.basename(a.file), a.host, a.port)
    return 0


def cmd_check(a):
    stmts = parse_program(read_file(a.file), os.path.basename(a.file))
    kinds = {}
    for s in stmts:
        kinds[s["k"]] = kinds.get(s["k"], 0) + 1
    print("OK  %s  (screen: %d, fungsi: %d, import: %d, style: %d)" % (
        a.file, kinds.get("screen", 0), kinds.get("def", 0), kinds.get("import", 0), kinds.get("style", 0)))
    return 0


def cmd_new(a):
    name = a.name
    os.makedirs(name, exist_ok=True)
    path = os.path.join(name, "main.kd")
    if os.path.exists(path):
        print("%s sudah ada." % path, file=sys.stderr)
        return 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(SCAFFOLD.format(name=name))
    print("Proyek dibuat: %s\nJalankan: kodo run %s   atau   kodo serve %s" % (path, path, path))
    return 0


def cmd_repl(a):
    from .term import TermIO
    it = Interpreter(TermIO())
    it.repl = True
    print("Kodo %s REPL - ketik exit untuk keluar" % __version__)
    buf, depth = [], 0
    while True:
        try:
            line = input("kodo> " if not buf else "  ... ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not buf and line.strip() in ("exit", "quit"):
            break
        buf.append(line)
        depth += brace_delta(line)
        if depth > 0:
            continue
        src, buf, depth = "\n".join(buf), [], 0
        try:
            it.load_source(src, "<repl>")
        except KodoError as e:
            print(e)
        except QuitSignal:
            break
    return 0


def main(argv=None):
    sys.setrecursionlimit(6000)
    ap = argparse.ArgumentParser(prog="kodo", description="Kodo %s - bahasa pembuat aplikasi (.kd)" % __version__)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("run", help="jalankan file .kd di terminal (atau --web)")
    p.add_argument("file")
    p.add_argument("--web", action="store_true")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("serve", help="jalankan sebagai aplikasi web di localhost")
    p.add_argument("file")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("check", help="cek sintaks file .kd")
    p.add_argument("file")
    p = sub.add_parser("new", help="buat proyek baru")
    p.add_argument("name")
    sub.add_parser("repl", help="interpreter interaktif")
    sub.add_parser("version", help="versi Kodo")
    a = ap.parse_args(argv)
    fn = {"run": cmd_run, "serve": cmd_serve, "check": cmd_check, "new": cmd_new,
          "repl": cmd_repl}.get(a.cmd)
    if a.cmd == "version":
        print("Kodo %s" % __version__)
        return
    if not fn:
        ap.print_help()
        return
    try:
        code = fn(a)
    except KodoError as e:
        print(e, file=sys.stderr)
        code = 1
    except QuitSignal:
        code = 0
    except KeyboardInterrupt:
        code = 130
    sys.exit(code or 0)
