"""Interpreter Kodo: eksekusi statement, bangun view tree untuk screen."""
import os
import re
import random
import time

from .errors import (KodoError, ReturnSignal, BreakSignal, ContinueSignal,
                     QuitSignal, NeedInput)
from .expr import evaluate, fmt, num, eq, add_values, arith, contains
from .parser import parse_program
from .style import Style

TEXT_EXT = (".txt", ".json", ".csv", ".md", ".list")
COMP_ACTIONS = ("show", "makevisible", "hide", "remove", "toggle")
MAX_LOOP = 1000000


class NullIO(object):
    def print(self, s):
        print(s)

    def prompt(self, name, label):
        return input(label)


def _slug(s):
    return re.sub(r"\W+", "_", s.strip().lower()).strip("_") or "input"


def _a(args, i, name):
    if len(args) <= i:
        raise KodoError("%s() butuh argumen ke-%d" % (name, i + 1))
    return args[i]


def _type(it, a):
    v = _a(a, 0, "type")
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def _sort(it, a):
    v = _a(a, 0, "sort")
    try:
        return sorted(v)
    except TypeError:
        return sorted(v, key=fmt)


def _minmax(f, name):
    def g(it, a):
        seq = a[0] if len(a) == 1 and isinstance(a[0], list) else a
        if not seq:
            raise KodoError("%s() butuh nilai" % name)
        return f(num(x) for x in seq)
    return g


def _range(it, a):
    n = [int(num(x)) for x in a]
    if not n:
        raise KodoError("range() butuh argumen")
    return list(range(*n))


def _push(it, a):
    lst = _a(a, 0, "push")
    if not isinstance(lst, list):
        raise KodoError("push() butuh array")
    lst.append(_a(a, 1, "push"))
    return lst


def _pop(it, a):
    lst = _a(a, 0, "pop")
    if not isinstance(lst, list) or not lst:
        raise KodoError("pop() butuh array tidak kosong")
    return lst.pop(int(num(a[1])) if len(a) > 1 else -1)


def _input(it, a):
    label = fmt(a[0]) if a else ""
    return it.io.prompt("_" + _slug(label), label)


def _goto(it, a):
    it.goto(fmt(_a(a, 0, "goto")))


def _quit(it, a):
    raise QuitSignal()


def _round(it, a):
    n = num(_a(a, 0, "round"))
    d = int(num(a[1])) if len(a) > 1 else 0
    r = round(n, d)
    return int(r) if d == 0 else r


BUILTINS = {
    "len": lambda it, a: len(_a(a, 0, "len")) if _a(a, 0, "len") is not None else 0,
    "str": lambda it, a: fmt(_a(a, 0, "str")),
    "num": lambda it, a: num(_a(a, 0, "num")),
    "int": lambda it, a: int(num(_a(a, 0, "int"))),
    "float": lambda it, a: float(num(_a(a, 0, "float"))),
    "upper": lambda it, a: fmt(_a(a, 0, "upper")).upper(),
    "lower": lambda it, a: fmt(_a(a, 0, "lower")).lower(),
    "trim": lambda it, a: fmt(_a(a, 0, "trim")).strip(),
    "round": _round,
    "abs": lambda it, a: abs(num(_a(a, 0, "abs"))),
    "min": _minmax(min, "min"),
    "max": _minmax(max, "max"),
    "sum": lambda it, a: sum(num(x) for x in _a(a, 0, "sum")),
    "range": _range,
    "push": _push,
    "pop": _pop,
    "join": lambda it, a: fmt(_a(a, 1, "join")).join(fmt(x) for x in _a(a, 0, "join")),
    "split": lambda it, a: fmt(_a(a, 0, "split")).split(fmt(a[1]) if len(a) > 1 else None),
    "replace": lambda it, a: fmt(_a(a, 0, "replace")).replace(fmt(_a(a, 1, "replace")), fmt(_a(a, 2, "replace"))),
    "contains": lambda it, a: contains(_a(a, 0, "contains"), _a(a, 1, "contains")),
    "keys": lambda it, a: list(_a(a, 0, "keys").keys()),
    "sort": _sort,
    "reverse": lambda it, a: list(reversed(_a(a, 0, "reverse"))),
    "type": _type,
    "random": lambda it, a: random.random(),
    "randint": lambda it, a: random.randint(int(num(_a(a, 0, "randint"))), int(num(_a(a, 1, "randint")))),
    "now": lambda it, a: time.strftime("%H:%M:%S"),
    "today": lambda it, a: time.strftime("%Y-%m-%d"),
    "file": lambda it, a: it.file_lines(fmt(_a(a, 0, "file"))),
    "input": _input,
    "toast": lambda it, a: it.emit(fmt(_a(a, 0, "toast"))),
    "alert": lambda it, a: it.emit(fmt(_a(a, 0, "alert"))),
    "back": lambda it, a: it.back(),
    "goto": _goto,
    "open": _goto,
    "quit": _quit,
    "exit": _quit,
}


def walk_ui(stmts):
    for s in stmts:
        k = s["k"]
        if k == "ui":
            yield s
        elif k == "layout" or k in ("loop", "for"):
            for x in walk_ui(s["body"]):
                yield x
        elif k == "if":
            for _, b in s["branches"]:
                for x in walk_ui(b):
                    yield x
            for x in walk_ui(s["else"] or []):
                yield x


class Interpreter(object):
    def __init__(self, io=None, base_dir=".", file="<kodo>"):
        self.io = io or NullIO()
        self.base = base_dir
        self.file = file
        self.g = {}
        self.frames = []
        self.funcs = {}
        self.screens = {}
        self.first_screen = None
        self.style = Style()
        self.files = {}
        self.assets = []
        self.urls = []
        self.loaded = set()
        self.stack = []
        self.current = None
        self.hidden = set()
        self.removed = set()
        self.cur_ids = set()
        self.handlers = {}
        self.captures = []
        self.depth = 0
        self.repl = False

    # ------------------------------------------------------------ variabel
    def get(self, name):
        for f in reversed(self.frames):
            if name in f:
                return f[name]
        if name in self.g:
            return self.g[name]
        raise KodoError("variabel '%s' belum dibuat" % name)

    def lookup_opt(self, name):
        try:
            return self.get(name)
        except KodoError:
            return None

    def define(self, name, val):
        (self.frames[-1] if self.frames else self.g)[name] = val

    def set_var(self, name, val):
        for f in reversed(self.frames):
            if name in f:
                f[name] = val
                return
        if name in self.g or not self.frames:
            self.g[name] = val
        else:
            self.frames[-1][name] = val

    def snapshot(self):
        d = {}
        for f in self.frames:
            d.update(f)
        return d

    # ------------------------------------------------------------- loading
    def load_source(self, src, file=None):
        prev = self.file
        self.file = file or self.file
        try:
            stmts = parse_program(src, self.file)
            for s in stmts:
                k = s["k"]
                if k == "def":
                    self.funcs[s["name"]] = s
                elif k == "screen":
                    self.screens[s["name"]] = s
                    if self.first_screen is None:
                        self.first_screen = s["name"]
                elif k == "style":
                    self.style.add_rules(s["rules"])
                elif k == "import":
                    self.do_import(s)
            for s in stmts:
                if s["k"] in ("def", "screen", "style", "import"):
                    continue
                val = self.exec_stmt(s, None)
                if self.repl and s["k"] == "expr" and val is not None:
                    self.io.print(fmt(val))
        finally:
            self.file = prev

    def do_import(self, s):
        spec = s["spec"]
        if re.match(r"https?://", spec):
            self.urls.append(spec)
            return
        ext = os.path.splitext(spec)[1].lower()
        path = os.path.join(self.base, spec)
        if ext == ".kd":
            key = os.path.abspath(path)
            if key in self.loaded:
                return
            self.loaded.add(key)
            try:
                with open(path, encoding="utf-8") as f:
                    self.load_source(f.read(), spec)
            except OSError:
                raise KodoError("modul '%s' tidak ditemukan" % spec, s["line"], self.file)
        elif ext in TEXT_EXT:
            try:
                with open(path, encoding="utf-8") as f:
                    self.files[spec] = f.read()
            except OSError:
                raise KodoError("file import '%s' tidak ditemukan" % spec, s["line"], self.file)
        else:
            self.assets.append(spec)

    def file_lines(self, name):
        text = self.files.get(name)
        if text is None:
            text = self.files.get(os.path.basename(name))
        if text is None:
            try:
                with open(os.path.join(self.base, name), encoding="utf-8") as f:
                    text = f.read()
            except OSError:
                raise KodoError("file '%s' tidak ditemukan (pakai: import %s)" % (name, name))
            self.files[name] = text
        return [l.strip() for l in text.splitlines() if l.strip()]

    # ------------------------------------------------------------ eksekusi
    def emit(self, s):
        if self.captures:
            self.captures[-1].append(s)
        else:
            self.io.print(s)

    def exec_block(self, stmts, out):
        for s in stmts:
            self.exec_stmt(s, out)

    def exec_stmt(self, s, out):
        try:
            return self._exec(s, out)
        except KodoError as e:
            if e.line is None:
                e.line, e.file = s.get("line"), self.file
            raise

    def _exec(self, s, out):
        k = s["k"]
        if k == "let":
            self.define(s["name"], evaluate(s["e"], self))
        elif k == "state":
            if s["name"] not in self.g:
                self.g[s["name"]] = evaluate(s["e"], self)
        elif k == "assign":
            self.do_assign(s)
        elif k == "if":
            for cond, body in s["branches"]:
                if evaluate(cond, self):
                    self.exec_block(body, out)
                    return
            if s["else"]:
                self.exec_block(s["else"], out)
        elif k == "loop":
            c = evaluate(s["count"], self)
            seq = c if isinstance(c, list) else range(1, int(num(c)) + 1)
            self.run_loop(s, seq, out)
        elif k == "for":
            c = evaluate(s["over"], self)
            if isinstance(c, dict):
                c = list(c.keys())
            elif isinstance(c, str):
                c = list(c)
            elif isinstance(c, (int, float)) and not isinstance(c, bool):
                c = range(1, int(c) + 1)
            elif c is None:
                c = []
            self.run_loop(s, c, out)
        elif k == "print":
            self.emit(fmt(evaluate(s["e"], self)))
        elif k == "return":
            raise ReturnSignal(evaluate(s["e"], self))
        elif k == "break":
            raise BreakSignal()
        elif k == "continue":
            raise ContinueSignal()
        elif k == "expr":
            return evaluate(s["e"], self)
        elif k == "ui":
            if out is None:
                self.func_ui(s)
            else:
                self.build_ui(s, out)
        elif k == "layout":
            self.do_layout(s, out)
        elif k in ("def", "screen", "style", "import"):
            raise KodoError("'%s' hanya boleh di level atas file" % k)
        else:
            raise KodoError("statement tidak dikenal: %s" % k)

    def run_loop(self, s, seq, out):
        n = 0
        for v in seq:
            n += 1
            if n > MAX_LOOP:
                raise KodoError("loop terlalu panjang (>%d)" % MAX_LOOP)
            if s["var"]:
                self.define(s["var"], v)
            try:
                self.exec_block(s["body"], out)
            except ContinueSignal:
                continue
            except BreakSignal:
                break

    def do_assign(self, s):
        name, op = s["name"], s["op"]
        val = evaluate(s["e"], self)
        if s["idx"] is not None:
            cont = self.get(name)
            i = evaluate(s["idx"], self)
            key = fmt(i) if isinstance(cont, dict) else int(num(i))
            try:
                old = cont[key] if op != "=" else None
                cont[key] = self.combine(op, old, val)
            except (IndexError, TypeError):
                raise KodoError("index %s tidak valid" % fmt(i))
            return
        old = self.get(name) if op != "=" else None
        self.set_var(name, self.combine(op, old, val))

    @staticmethod
    def combine(op, old, val):
        if op == "=":
            return val
        if op == "+=":
            return add_values(old, val)
        return arith(op[0], old, val)

    # ---------------------------------------------------------- fungsi
    def call(self, name, args):
        f = self.funcs.get(name)
        if f:
            return self.call_func(f, args)
        b = BUILTINS.get(name)
        if b:
            return b(self, args)
        if name in self.screens:
            self.goto(name)
            return None
        raise KodoError("fungsi '%s' belum dibuat" % name)

    def call_func(self, f, args):
        if self.depth > 100:
            raise KodoError("rekursi terlalu dalam")
        frame = dict((p, args[i] if i < len(args) else None) for i, p in enumerate(f["params"]))
        saved = self.frames
        self.frames = [frame]
        self.depth += 1
        try:
            self.exec_block(f["body"], None)
        except ReturnSignal as r:
            return r.value
        finally:
            self.frames = saved
            self.depth -= 1
        return None

    def run_capture(self, name, args):
        self.captures.append([])
        try:
            ret = self.call(name, args)
        finally:
            cap = self.captures.pop()
        if ret is not None:
            cap = cap + [fmt(ret)]
        return "\n".join(cap)

    def func_ui(self, s):
        kind = s["kind"]
        val = evaluate(s["value"], self) if s["value"] is not None else None
        if kind in ("text", "title", "link"):
            self.emit(fmt(val))
        elif kind == "input" or (kind == "button" and not s["event"] and not s["call"]):
            name = s["id"] or _slug(fmt(val))
            self.define(name, self.io.prompt(name, fmt(val)))
        elif kind == "image":
            self.emit("[gambar: %s]" % fmt(val))

    # ---------------------------------------------------------- screen
    def start(self):
        for n in ("main", "home", "start", "app"):
            if n in self.screens:
                self.current = n
                break
        else:
            self.current = self.first_screen
        if self.current is None:
            raise KodoError("tidak ada void.screen untuk ditampilkan")
        self.enter_screen()

    def enter_screen(self):
        self.hidden, self.removed = set(), set()
        ids, targets = set(), set()
        for u in walk_ui(self.screens[self.current]["body"]):
            if u["id"]:
                ids.add(u["id"])
            if u["event"] and u["call"] and u["action"] in ("show", "makevisible"):
                targets.add(u["call"][0])
        self.hidden |= (targets & ids)

    def goto(self, name):
        if name not in self.screens:
            raise KodoError("screen '%s' tidak ada" % name)
        self.stack.append(self.current)
        self.current = name
        self.enter_screen()

    def back(self):
        if self.stack:
            self.current = self.stack.pop()
            self.enter_screen()

    def render(self):
        scr = self.screens[self.current]
        self.handlers = {}
        self.cur_ids = set()
        root = {"type": "screen", "name": self.current, "children": []}
        saved = self.frames
        self.frames = [{}]
        try:
            self.exec_block(scr["body"], root["children"])
        finally:
            self.frames = saved
        return root

    def reg(self, kind, ident, event, call, action):
        hid = "h%d" % len(self.handlers)
        self.handlers[hid] = {"input": ident if kind == "input" else None, "call": call,
                              "action": action, "event": event, "scope": self.snapshot()}
        return hid

    def build_ui(self, s, out):
        kind, ident = s["kind"], s["id"]
        if ident:
            self.cur_ids.add(ident)
            if ident in self.removed or ident in self.hidden:
                return
        val = evaluate(s["value"], self) if s["value"] is not None else None
        node = {"type": kind, "id": ident, "handlers": {}}
        if kind == "input":
            if ident and self.lookup_opt(ident) is None and ident not in self.g:
                self.g[ident] = ""
            node["label"] = fmt(val)
            node["value"] = fmt(self.lookup_opt(ident)) if ident else ""
            node["handlers"]["onchange"] = self.reg(kind, ident, "onchange", s["call"], s["action"])
        elif kind == "image":
            node["src"] = fmt(val)
        elif kind != "divider":
            node["text"] = fmt(val)
        call = s["call"]
        if call and s["event"] and kind != "input":
            node["handlers"][s["event"]] = self.reg(kind, ident, s["event"], call, s["action"])
        elif call and s["action"] == "show" and not s["event"]:
            try:
                res = self.run_capture(call[0], [evaluate(a, self) for a in call[1]])
            except NeedInput as e:
                node["need"] = {"name": e.name, "label": e.label}
                res = ""
            node["text"] = (node.get("text") or "") + res
        out.append(node)

    def do_layout(self, s, out):
        kind = s["kind"]
        node = {"type": kind, "id": None, "children": []}
        target = node["children"] if out is not None else None
        if out is not None:
            out.append(node)
        if kind == "list":
            seq = evaluate(s["over"], self)
            if seq is None:
                seq = []
            elif isinstance(seq, dict):
                seq = list(seq.values())
            elif not isinstance(seq, list):
                seq = [seq]
            self.frames.append({})
            try:
                for i, v in enumerate(seq, 1):
                    self.frames[-1]["item"] = v
                    self.frames[-1]["index"] = i
                    self.exec_block(s["body"], target)
            finally:
                self.frames.pop()
        else:
            self.exec_block(s["body"], target)

    def fire(self, hid, value=None):
        h = self.handlers.get(hid)
        if not h:
            return
        if h["input"]:
            self.g[h["input"]] = "" if value is None else value
        call = h["call"]
        if not call:
            return
        name, arg_asts = call
        saved = self.frames
        self.frames = [dict(h["scope"])]
        try:
            args = [evaluate(a, self) for a in arg_asts]
        finally:
            self.frames = saved
        f = self.funcs.get(name)
        if not args and value is not None and f and f["params"]:
            args = [value]
        action = h["action"]
        if name in self.cur_ids and action in COMP_ACTIONS:
            if action in ("show", "makevisible"):
                self.hidden.discard(name)
            elif action == "hide":
                self.hidden.add(name)
            elif action == "remove":
                self.removed.add(name)
            else:
                (self.hidden.discard if name in self.hidden else self.hidden.add)(name)
        elif action == "show":
            txt = self.run_capture(name, args)
            if txt:
                self.emit(txt)
        else:
            self.call(name, args)
