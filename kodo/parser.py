"""Parser statement Kodo -> list of dict. Hoisting dilakukan interpreter."""
import re
from .errors import KodoError
from .lexer import build_tree
from .expr import parse_expr

KINDS = ("text", "title", "image", "button", "input", "link", "divider")
LAYOUTS = ("column", "row", "box", "card")
EVENTS = ("onclick", "onhold", "onchange")

R_NET = re.compile(r"^(net|state)\s+([A-Za-z_]\w*)\s*(?:=\s*(.*))?$")
R_SCREEN = re.compile(r"^void\.(?:screen\s+)?([A-Za-z_]\w*)\s*$")
R_VOID = re.compile(r"^void\s+([A-Za-z_]\w*)\s*\((.*)\)\s*$")
R_IMPORT = re.compile(r'^import\s+(?:"([^"]*)"|(\S+))\s*$')
R_IF = re.compile(r"^if\b\s*(.+?)(?:\s+then\b\s*(.*))?$")
R_ELIF = re.compile(r"^(?:elseif|elif|else\s+if)\b\s*(.+?)(?:\s+then\b\s*(.*))?$")
R_ELSE = re.compile(r"^else\b\s*(?:then\b)?\s*(.*)$")
R_FOR = re.compile(r"^loop\.for\s+([A-Za-z_]\w*)\s*(?:\.|\s+in\s+|\s+)\s*(.+)$")
R_LOOPN = re.compile(r"^loop\.([A-Za-z_]\w*)\s+([^\s\-+*/%<>=!&|].*)$")
R_LOOP = re.compile(r"^loop\.(.+)$")
R_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*(?:\[(.+)\])?\s*(\+=|-=|\*=|/=|=)\s*(.+)$")
R_INCR = re.compile(r"^([A-Za-z_]\w*)\s*(\+\+|--)$")
R_PRINT = re.compile(r"^(?:print|say)\b\s*(.*)$")
R_RETURN = re.compile(r"^return\b\s*(.*)$")
R_LAYOUT = re.compile(r"^(column|row|box|card)\s*$")
R_LIST = re.compile(r"^list\s+(.+)$")
UI_SEMI = re.compile(r"^[A-Za-z_]\w*\s*;")
UI_KIND = re.compile(r"^(?:text|title|image|button|input|link|divider)\b(?!\s*[=(.\[])")
ID_SPLIT = re.compile(r"^([A-Za-z_]\w*)(?:\.|\s+)(?=[\"'A-Za-z_0-9(\[.-])(.*)$", re.S)
CHAIN_START = re.compile(r"\.(?:onclick|onhold|onchange|show)\b")


def E(text, ln, file):
    try:
        return parse_expr(text.strip())
    except KodoError as e:
        if e.line is None:
            e.line, e.file = ln, file
        raise


def split_top(s, sep):
    out, cur, depth, q, i = [], [], 0, None, 0
    while i < len(s):
        c = s[i]
        if q:
            cur.append(c)
            if c == "\\" and i + 1 < len(s):
                cur.append(s[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c in "\"'":
            q = c
            cur.append(c)
        elif c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth -= 1
            cur.append(c)
        elif c == sep and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur))
    return out


def find_chain(rest):
    depth, q, i = 0, None, 0
    while i < len(rest):
        c = rest[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "." and depth == 0 and CHAIN_START.match(rest, i):
            return i
        i += 1
    return -1


def parse_args(s, ln, file):
    return [E(x, ln, file) for x in split_top(s, ",") if x.strip()]


def parse_chain(chain, ln, file):
    event = action = call = None
    for p in split_top(chain.strip().lstrip("."), "."):
        p = p.strip()
        if not p:
            continue
        mc = re.match(r"^([\w\-]+)\s*\((.*)\)$", p, re.S)
        if mc:
            call = (mc.group(1), parse_args(mc.group(2), ln, file))
        elif p in EVENTS:
            event = p
        else:
            action = p
    if call and event and not action:
        action = "active"
    return event, action, call


def parse_ui(t, ln, file):
    kind = ident = None
    m = re.match(r"^(\w+)\s*;\s*(.*)$", t)
    if m:
        first, rest = m.group(1), m.group(2)
        if first in KINDS:
            kind = first
            m2 = ID_SPLIT.match(rest)
            if m2 and not rest.startswith(('"', "'")):
                ident, rest = m2.group(1), m2.group(2)
        else:
            ident = first
            kind = "input" if rest.startswith("input(") else "text"
    else:
        m = re.match(r"^(\w+)\s*(.*)$", t, re.S)
        kind, rest = m.group(1), m.group(2)
    idx = find_chain(rest)
    value_text, chain = (rest[:idx], rest[idx:]) if idx >= 0 else (rest, "")
    value = E(value_text, ln, file) if value_text.strip() else None
    if value is not None and value[0] == "call" and value[1] == "input":
        kind = "input"
        value = value[2][0] if value[2] else ("lit", "")
    event, action, call = parse_chain(chain, ln, file) if chain else (None, None, None)
    return {"k": "ui", "kind": kind, "id": ident, "value": value, "event": event,
            "action": action, "call": call, "line": ln}


def strip_q(v):
    v = v.strip().rstrip(";").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return v


def parse_style(node):
    rules, loose = [], []

    def props(kids):
        out = []
        for k in kids:
            m = re.match(r"^([\w\.\-]+)\s*(?:;|:|=)\s*(.+?)\s*;?$", k.text)
            if m:
                out.append((m.group(1), strip_q(m.group(2))))
        return out

    for k in node.kids:
        if k.kids:
            ms = re.match(r"^([\w\.\*\-#]+)\s*;?\s*$", k.text)
            if ms:
                rules.append((ms.group(1), props(k.kids)))
        else:
            loose.append(k)
    if loose:
        rules.insert(0, ("*", props(loose)))
    return {"k": "style", "rules": rules, "line": node.line}


def parse_block(kids, file):
    out, i = [], 0
    while i < len(kids):
        ln = kids[i].line
        try:
            st, i = parse_one(kids, i, file)
        except KodoError as e:
            if e.line is None:
                e.line, e.file = ln, file
            raise
        if st is not None:
            out.append(st)
    return out


def parse_inline(text, ln, file):
    from .lexer import Node
    return parse_block([Node(text, ln)], file)


def parse_one(kids, i, file):
    node = kids[i]
    t, ln, body = node.text, node.line, node.kids
    nxt = i + 1

    m = R_NET.match(t)
    if m:
        e = E(m.group(3), ln, file) if m.group(3) else ("lit", None)
        return {"k": "state" if m.group(1) == "state" else "let", "name": m.group(2), "e": e, "line": ln}, nxt
    m = R_SCREEN.match(t)
    if m:
        if m.group(1) == "style":
            return parse_style(node), nxt
        return {"k": "screen", "name": m.group(1), "body": parse_block(body, file), "line": ln}, nxt
    m = R_VOID.match(t)
    if m:
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        return {"k": "def", "name": m.group(1), "params": params, "body": parse_block(body, file), "line": ln}, nxt
    m = R_IMPORT.match(t)
    if m:
        return {"k": "import", "spec": m.group(1) if m.group(1) is not None else m.group(2), "line": ln}, nxt
    if t in ("break", "continue"):
        return {"k": t, "line": ln}, nxt
    m = R_IF.match(t)
    if m:
        def split_else(txt):
            for mm in re.finditer(r"\s+else\s+", txt):
                if txt[:mm.start()].count('"') % 2 == 0:
                    return txt[:mm.start()], txt[mm.end():]
            return txt, None
        inline_else = None
        if m.group(2):
            a, inline_else = split_else(m.group(2))
            m = type("M", (), {"group": lambda self, i, _m=m, _a=a: _a if i == 2 else _m.group(i)})()

        def branch(cond, inline, node_):
            b = parse_inline(inline, node_.line, file) if inline else parse_block(node_.kids, file)
            return (E(cond, node_.line, file), b)
        branches = [branch(m.group(1), m.group(2), node)]
        els = parse_inline(inline_else, ln, file) if inline_else else None
        while nxt < len(kids) and els is None:
            n2 = kids[nxt]
            m2 = R_ELIF.match(n2.text)
            if m2:
                branches.append(branch(m2.group(1), m2.group(2), n2))
                nxt += 1
                continue
            m3 = R_ELSE.match(n2.text)
            if m3:
                els = parse_inline(m3.group(1), n2.line, file) if m3.group(1) else parse_block(n2.kids, file)
                nxt += 1
            break
        return {"k": "if", "branches": branches, "else": els, "line": ln}, nxt
    m = R_FOR.match(t)
    if m:
        return {"k": "for", "var": m.group(1), "over": E(m.group(2), ln, file), "body": parse_block(body, file), "line": ln}, nxt
    m = R_LOOPN.match(t)
    if m:
        return {"k": "loop", "var": m.group(1), "count": E(m.group(2), ln, file), "body": parse_block(body, file), "line": ln}, nxt
    m = R_LOOP.match(t)
    if m:
        return {"k": "loop", "var": None, "count": E(m.group(1), ln, file), "body": parse_block(body, file), "line": ln}, nxt
    m = R_PRINT.match(t)
    if m:
        return {"k": "print", "e": E(m.group(1), ln, file) if m.group(1) else ("lit", ""), "line": ln}, nxt
    m = R_RETURN.match(t)
    if m:
        return {"k": "return", "e": E(m.group(1), ln, file) if m.group(1) else ("lit", None), "line": ln}, nxt
    m = R_LAYOUT.match(t)
    if m:
        return {"k": "layout", "kind": m.group(1), "over": None, "body": parse_block(body, file), "line": ln}, nxt
    m = R_LIST.match(t)
    if m and body is not None and (body or True):
        return {"k": "layout", "kind": "list", "over": E(m.group(1), ln, file), "body": parse_block(body, file), "line": ln}, nxt
    if UI_SEMI.match(t) or UI_KIND.match(t):
        return parse_ui(t, ln, file), nxt
    m = R_INCR.match(t)
    if m:
        return {"k": "assign", "name": m.group(1), "idx": None, "op": "+=" if m.group(2) == "++" else "-=", "e": ("lit", 1), "line": ln}, nxt
    m = R_ASSIGN.match(t)
    if m:
        return {"k": "assign", "name": m.group(1), "idx": E(m.group(2), ln, file) if m.group(2) else None,
                "op": m.group(3), "e": E(m.group(4), ln, file), "line": ln}, nxt
    return {"k": "expr", "e": E(t, ln, file), "line": ln}, nxt


def parse_program(source, file=None):
    root = build_tree(source)
    return parse_block(root.kids, file)
