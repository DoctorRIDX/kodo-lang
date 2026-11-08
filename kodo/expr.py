"""Ekspresi Kodo: tokenizer, parser (AST tuple), evaluator."""
import re
from .errors import KodoError

_FILE_IN = re.compile(r'\bin\s+([\w\-/]+\.(?:txt|json|csv|md|list))\b')
_EQ_IN = re.compile(r'(?:==|=)\s*in\s+')
_TOKEN = re.compile(
    r"""\s*(?:(?P<num>\d+(?:\.\d+)?)"""
    r"""|(?P<str>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""
    r"""|(?P<op>==|!=|>=|<=|&&|\|\||[-+*/%<>=!(),\[\]\.{}:])"""
    r"""|(?P<id>[A-Za-z_]\w*))"""
)
_AND = ("and", "dan")
_OR = ("or", "atau")
_NOT = ("not", "bukan")
_INTERP = re.compile(r"\{([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\}")


def tokenize(text):
    text = _EQ_IN.sub("in ", text)
    text = _FILE_IN.sub(lambda m: 'in file("%s")' % m.group(1), text)
    pos = 0
    out = []
    while True:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise KodoError("karakter tidak dikenal: %r" % text[pos:].strip()[:12])
        pos = m.end()
        out.append((m.lastgroup, m.group(m.lastgroup)))
    return out


def unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s[1:-1])


class _P(object):
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def op(self, *ops):
        k, v = self.peek()
        if k == "op" and v in ops:
            self.i += 1
            return v
        return None

    def kw(self, words):
        k, v = self.peek()
        if k == "id" and v.lower() in words:
            self.i += 1
            return True
        return False

    def expect(self, o):
        if not self.op(o):
            raise KodoError("diharapkan '%s'" % o)

    def parse(self):
        if not self.t:
            raise KodoError("ekspresi kosong")
        e = self.or_()
        if self.i < len(self.t):
            raise KodoError("ekspresi tidak valid dekat %r" % (self.peek()[1],))
        return e

    def or_(self):
        l = self.and_()
        while self.op("||") or self.kw(_OR):
            l = ("bin", "or", l, self.and_())
        return l

    def and_(self):
        l = self.not_()
        while self.op("&&") or self.kw(_AND):
            l = ("bin", "and", l, self.not_())
        return l

    def not_(self):
        if self.op("!") or self.kw(_NOT):
            return ("un", "not", self.not_())
        return self.cmp()

    def cmp(self):
        l = self.add()
        while True:
            o = self.op("==", "!=", ">=", "<=", ">", "<", "=")
            if o:
                l = ("bin", "==" if o == "=" else o, l, self.add())
                continue
            k, v = self.peek()
            if k == "id" and v.lower() == "in":
                self.i += 1
                l = ("bin", "in", l, self.add())
                continue
            return l

    def add(self):
        l = self.mul()
        while True:
            o = self.op("+", "-")
            if not o:
                return l
            l = ("bin", o, l, self.mul())

    def mul(self):
        l = self.unary()
        while True:
            o = self.op("*", "/", "%")
            if not o:
                return l
            l = ("bin", o, l, self.unary())

    def unary(self):
        if self.op("-"):
            return ("un", "neg", self.unary())
        return self.postfix()

    def args(self):
        out = []
        if self.op(")"):
            return out
        while True:
            out.append(self.or_())
            if self.op(","):
                continue
            self.expect(")")
            return out

    def postfix(self):
        e = self.primary()
        while True:
            if self.op("."):
                k, v = self.peek()
                if k != "id":
                    raise KodoError("nama diharapkan setelah '.'")
                self.i += 1
                if self.peek() == ("op", "("):
                    self.i += 1
                    e = ("mcall", e, v, self.args())
                else:
                    e = ("attr", e, v)
            elif self.peek() == ("op", "(") and e[0] == "var":
                self.i += 1
                e = ("call", e[1], self.args())
            elif self.op("["):
                idx = self.or_()
                self.expect("]")
                e = ("idx", e, idx)
            else:
                return e

    def primary(self):
        k, v = self.peek()
        if k is None:
            raise KodoError("ekspresi belum lengkap")
        self.i += 1
        if k == "num":
            return ("lit", float(v) if "." in v else int(v))
        if k == "str":
            return ("str", unescape(v))
        if k == "id":
            lv = v.lower()
            if lv in ("true", "benar"):
                return ("lit", True)
            if lv in ("false", "salah"):
                return ("lit", False)
            if lv in ("null", "none", "kosong"):
                return ("lit", None)
            return ("var", v)
        if k == "op":
            if v == "(":
                e = self.or_()
                self.expect(")")
                return e
            if v == "[":
                items = []
                if not self.op("]"):
                    while True:
                        items.append(self.or_())
                        if self.op(","):
                            continue
                        self.expect("]")
                        break
                return ("list", items)
            if v == "{":
                pairs = []
                if not self.op("}"):
                    while True:
                        key = self.or_()
                        if key[0] == "var":
                            key = ("lit", key[1])
                        self.expect(":")
                        pairs.append((key, self.or_()))
                        if self.op(","):
                            continue
                        self.expect("}")
                        break
                return ("dict", pairs)
        raise KodoError("token tidak terduga: %r" % v)


_cache = {}


def parse_expr(text):
    r = _cache.get(text)
    if r is None:
        r = _cache[text] = _P(tokenize(text)).parse()
    return r


# ---------------------------------------------------------------- evaluasi
def fmt(v):
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float):
        try:
            if v == int(v) and abs(v) < 1e15:
                return str(int(v))
        except (OverflowError, ValueError):
            pass
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (k, fmt(x)) for k, x in v.items()) + "}"
    return str(v)


def num(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if v is None or v == "":
        return 0
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            try:
                return float(v)
            except ValueError:
                pass
    raise KodoError("'%s' bukan angka" % fmt(v))


def eq(a, b):
    return a == b or fmt(a) == fmt(b)


def add_values(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return fmt(a) + fmt(b)
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    return num(a) + num(b)


def arith(op, a, b):
    a, b = num(a), num(b)
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if b == 0:
        raise KodoError("pembagian dengan nol")
    if op == "%":
        return a % b
    if isinstance(a, int) and isinstance(b, int) and a % b == 0:
        return a // b
    return a / b


def _cmpv(a, b):
    try:
        return num(a), num(b)
    except KodoError:
        return fmt(a), fmt(b)


def contains(container, item):
    if container is None:
        return False
    if isinstance(container, list):
        return any(eq(x, item) for x in container)
    if isinstance(container, (str, dict)):
        return fmt(item) in container
    return False


def get_attr(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    if isinstance(obj, (list, str)):
        if name in ("length", "panjang"):
            return len(obj)
        if name == "first" and isinstance(obj, list):
            return obj[0] if obj else None
        if name == "last" and isinstance(obj, list):
            return obj[-1] if obj else None
    raise KodoError("tidak ada properti '%s' pada %s" % (name, fmt(obj) or "kosong"))


def interpolate(s, c):
    if "{" not in s:
        return s

    def rep(m):
        try:
            parts = m.group(1).split(".")
            v = c.get(parts[0])
            for p in parts[1:]:
                v = get_attr(v, p)
            return fmt(v)
        except KodoError:
            return m.group(0)
    return _INTERP.sub(rep, s)


def method(obj, name, args):
    try:
        if isinstance(obj, list):
            if name in ("push", "append"):
                obj.append(args[0])
                return obj
            if name == "pop":
                return obj.pop(int(num(args[0])) if args else -1)
            if name == "join":
                return (fmt(args[0]) if args else "").join(fmt(x) for x in obj)
            if name == "contains":
                return contains(obj, args[0])
            if name == "reverse":
                return list(reversed(obj))
            if name == "sort":
                try:
                    return sorted(obj)
                except TypeError:
                    return sorted(obj, key=fmt)
            if name in ("length", "count"):
                return len(obj)
        elif isinstance(obj, str):
            if name == "upper":
                return obj.upper()
            if name == "lower":
                return obj.lower()
            if name == "trim":
                return obj.strip()
            if name == "split":
                return obj.split(fmt(args[0]) if args else None)
            if name == "replace":
                return obj.replace(fmt(args[0]), fmt(args[1]))
            if name == "contains":
                return fmt(args[0]) in obj
            if name == "startswith":
                return obj.startswith(fmt(args[0]))
            if name == "endswith":
                return obj.endswith(fmt(args[0]))
            if name == "length":
                return len(obj)
        elif isinstance(obj, dict):
            if name == "keys":
                return list(obj.keys())
            if name == "values":
                return list(obj.values())
            if name == "has":
                return fmt(args[0]) in obj
            if name == "get":
                return obj.get(fmt(args[0]))
    except (IndexError, ValueError) as e:
        raise KodoError("argumen metode '%s' salah (%s)" % (name, e))
    raise KodoError("metode '%s' tidak dikenal untuk nilai ini" % name)


def evaluate(n, c):
    t = n[0]
    if t == "lit":
        return n[1]
    if t == "str":
        return interpolate(n[1], c)
    if t == "var":
        return c.get(n[1])
    if t == "list":
        return [evaluate(x, c) for x in n[1]]
    if t == "dict":
        return dict((fmt(evaluate(k, c)), evaluate(v, c)) for k, v in n[1])
    if t == "un":
        v = evaluate(n[2], c)
        return (not v) if n[1] == "not" else -num(v)
    if t == "bin":
        op = n[1]
        if op == "and":
            return bool(evaluate(n[2], c)) and bool(evaluate(n[3], c))
        if op == "or":
            return bool(evaluate(n[2], c)) or bool(evaluate(n[3], c))
        a = evaluate(n[2], c)
        b = evaluate(n[3], c)
        if op == "+":
            return add_values(a, b)
        if op in ("-", "*", "/", "%"):
            return arith(op, a, b)
        if op == "==":
            return eq(a, b)
        if op == "!=":
            return not eq(a, b)
        if op == "in":
            return contains(b, a)
        x, y = _cmpv(a, b)
        return {">": x > y, "<": x < y, ">=": x >= y, "<=": x <= y}[op]
    if t == "attr":
        return get_attr(evaluate(n[1], c), n[2])
    if t == "idx":
        obj = evaluate(n[1], c)
        i = evaluate(n[2], c)
        try:
            if isinstance(obj, dict):
                return obj.get(fmt(i))
            return obj[int(num(i))]
        except (IndexError, TypeError):
            raise KodoError("index %s di luar jangkauan" % fmt(i))
    if t == "call":
        return c.call(n[1], [evaluate(a, c) for a in n[2]])
    if t == "mcall":
        return method(evaluate(n[1], c), n[2], [evaluate(a, c) for a in n[3]])
    raise KodoError("node ekspresi tidak dikenal: %s" % t)
