"""UI terminal untuk screen Kodo (jalan di Termux)."""
import re
import sys

from .errors import KodoError, QuitSignal, NeedInput
from .style import to_rgb


class TermIO(object):
    def __init__(self):
        self.msgs = []
        self.buffering = False

    def print(self, s):
        if self.buffering:
            self.msgs.append(s)
        else:
            print(s)

    def prompt(self, name, label):
        return input(label)


def paint(text, props):
    codes = []
    rgb = to_rgb(props.get("color"))
    if rgb:
        codes.append("38;2;%d;%d;%d" % rgb)
    bg = to_rgb(props.get("background"))
    if bg:
        codes.append("48;2;%d;%d;%d" % bg)
    if props.get("font-weight") in ("700", "bold"):
        codes.append("1")
    if props.get("font-style") == "italic":
        codes.append("3")
    if not codes or not sys.stdout.isatty():
        return text
    return "\x1b[%sm%s\x1b[0m" % (";".join(codes), text)


def draw_children(it, children, items, indent):
    lines = []
    for c in children:
        lines += draw(it, c, items, indent)
    return lines


def draw(it, n, items, indent):
    t = n["type"]
    pad = "  " * indent
    st = it.style.props(t, n.get("id"))
    if t in ("column", "box", "card", "list"):
        return draw_children(it, n["children"], items, indent)
    if t == "row":
        parts = []
        for c in n["children"]:
            parts.append(" ".join(l.strip() for l in draw(it, c, items, 0)))
        return [pad + "   ".join(parts)]
    if t in ("text",):
        return [pad + paint(l, st) for l in n["text"].split("\n")]
    if t == "title":
        st = dict(st)
        st.setdefault("font-weight", "700")
        return [pad + paint(n["text"], st), pad + "─" * max(len(n["text"]), 3)]
    if t in ("button", "link"):
        items.append(n)
        return [pad + paint("[%d] %s" % (len(items), n["text"]), st)]
    if t == "input":
        items.append(n)
        return [pad + paint("[%d] %s %s" % (len(items), n["label"], n["value"] or "_____"), st)]
    if t == "image":
        return [pad + "🖼  " + n["src"]]
    if t == "divider":
        return [pad + "─" * 30]
    return []


def run_ui(it):
    io = it.io
    io.buffering = True
    it.start()
    tty = sys.stdout.isatty()
    while True:
        try:
            root = it.render()
        except QuitSignal:
            break
        except KodoError as e:
            io.buffering = False
            print(e, file=sys.stderr)
            return 1
        items = []
        lines = draw_children(it, root["children"], items, 0)
        if tty:
            sys.stdout.write("\x1b[2J\x1b[H")
        print(paint(" ◆ %s " % it.current.upper(), {"font-weight": "700", "color": "#a78bfa"}))
        print("─" * 40)
        print("\n".join(lines))
        print()
        for m in io.msgs:
            print("» " + m)
        io.msgs = []
        print("─" * 40)
        print("[no]=pilih  h[no]=tahan  b=kembali  r=segarkan  q=keluar")
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd in ("q", "quit", "exit"):
            break
        if cmd in ("b", "back"):
            it.back()
            continue
        if cmd in ("r", ""):
            continue
        m = re.match(r"^(h|hold)?\s*(\d+)$", cmd)
        if not (m and 1 <= int(m.group(2)) <= len(items)):
            io.msgs.append("perintah tidak dikenal: %s" % cmd)
            continue
        n = items[int(m.group(2)) - 1]
        hold = bool(m.group(1))
        try:
            if n["type"] == "input":
                it.fire(n["handlers"]["onchange"], input("%s " % n["label"]))
            else:
                hid = n["handlers"].get("onhold" if hold else "onclick")
                if hid:
                    it.fire(hid)
                else:
                    io.msgs.append("(tidak ada aksi %s di item ini)" % ("tahan" if hold else "klik"))
        except QuitSignal:
            break
        except (EOFError, KeyboardInterrupt):
            break
        except KodoError as e:
            io.msgs.append("⚠ " + str(e))
    io.buffering = False
    return 0
