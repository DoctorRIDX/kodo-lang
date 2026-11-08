"""Lexer berbasis baris: buang komentar, bangun pohon blok { }."""


class Node(object):
    __slots__ = ("text", "line", "kids")

    def __init__(self, text, line):
        self.text = text
        self.line = line
        self.kids = []


def strip_comment(line):
    out = []
    inq = False
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if inq:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(line[i + 1])
                i += 1
            elif c == '"':
                inq = False
        else:
            if c == '"':
                inq = True
                out.append(c)
            elif c == "/" and line[i:i + 2] == "//":
                break
            else:
                out.append(c)
        i += 1
    return "".join(out).strip()


def brace_delta(line):
    s = strip_comment(line)
    d = 0
    while s.startswith("}"):
        d -= 1
        s = s[1:].strip()
    if s.endswith("{"):
        d += 1
    return d


def build_tree(source):
    root = Node("", 0)
    stack = [root]
    for no, raw in enumerate(source.splitlines(), 1):
        t = strip_comment(raw)
        if not t:
            continue
        while t.startswith("}"):
            if len(stack) > 1:
                stack.pop()
            t = t[1:].strip()
        if not t:
            continue
        if t == "{":
            cur = stack[-1]
            if cur.kids:
                stack.append(cur.kids[-1])
            continue
        if t.endswith("{"):
            node = Node(t[:-1].strip(), no)
            stack[-1].kids.append(node)
            stack.append(node)
        else:
            stack[-1].kids.append(Node(t, no))
    return root  # blok yang lupa ditutup otomatis ditutup di akhir file
