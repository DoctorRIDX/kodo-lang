"""Blok style Kodo (mirip CSS) -> CSS untuk web & properti untuk terminal."""
import os
import re
import urllib.parse

NAMED = {
    "merah": "#e53935", "red": "#e53935", "hijau": "#43a047", "green": "#43a047",
    "biru": "#1e88e5", "blue": "#1e88e5", "kuning": "#fdd835", "yellow": "#fdd835",
    "putih": "#ffffff", "white": "#ffffff", "hitam": "#000000", "black": "#000000",
    "abu": "#9e9e9e", "gray": "#9e9e9e", "grey": "#9e9e9e", "ungu": "#8e24aa",
    "purple": "#8e24aa", "oranye": "#fb8c00", "orange": "#fb8c00", "pink": "#ec407a",
    "cyan": "#00acc1",
}
ALIAS = {
    "font": "font-family", "size": "font-size", "ukuran": "font-size", "warna": "color",
    "bg": "background", "radius": "border-radius", "bold": "font-weight", "tebal": "font-weight",
    "weight": "font-weight", "italic": "font-style", "miring": "font-style",
    "align": "text-align", "rata": "text-align", "shadow": "box-shadow",
}
PX = {"font-size", "width", "height", "padding", "margin", "border-radius", "gap", "max-width",
      "min-width", "min-height", "margin-top", "margin-bottom", "padding-top", "padding-bottom",
      "letter-spacing"}
FONT_EXT = (".ttf", ".otf", ".woff", ".woff2")
TRUE = ("true", "ya", "yes", "1", "bold", "tebal", "italic", "miring")


def norm_hex(v):
    m = re.fullmatch(r"#([0-9a-fA-F]+)", v.strip())
    if not m:
        return v
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) not in (6, 8):
        h = (h + h[-1] * 6)[:6]
    return "#" + h


def color(v):
    v = v.strip()
    return norm_hex(v) if v.startswith("#") else NAMED.get(v.lower(), v)


def to_rgb(v):
    if not v:
        return None
    v = color(v)
    m = re.fullmatch(r"#([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?", v)
    if not m:
        return None
    h = m.group(1)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class Style(object):
    def __init__(self):
        self.rules = []

    def add_rules(self, rules):
        self.rules.extend(rules)

    def decl(self, key, val, faces, imports):
        k = key.strip().lower()
        if k.startswith("set."):
            k = k[4:]
        k = ALIAS.get(k, k)
        v = val.strip()
        if k == "font-family":
            return self.font(v, faces, imports)
        if k in ("color", "background", "border-color", "outline-color"):
            v = color(v)
        elif k in PX:
            if re.fullmatch(r"-?\d+(\.\d+)?", v):
                v += "px"
        elif k == "font-weight":
            v = "700" if v.lower() in TRUE else ("400" if v.lower() in ("false", "no", "tidak", "normal", "0") else v)
        elif k == "font-style":
            v = "italic" if v.lower() in TRUE else "normal"
        return [(k, v)]

    def font(self, v, faces, imports):
        v = v.strip("\"'")
        if re.match(r"https?://", v) or v.lower().endswith(FONT_EXT):
            m = re.search(r"family=([^&:;]+)", v)
            fam = urllib.parse.unquote(m.group(1)).replace("+", " ") if m else None
            if v.lower().endswith(FONT_EXT):
                fam = os.path.splitext(os.path.basename(v))[0]
                url = v if v.startswith("http") else "/asset/" + urllib.parse.quote(v)
                faces.append("@font-face{font-family:'%s';src:url('%s')}" % (fam, url))
            elif m or v.lower().endswith(".css"):
                imports.append(v)
                fam = fam or "sans-serif"
            else:
                fam = None  # situs daftar font biasa: diabaikan
            return [("font-family", "'%s',sans-serif" % fam)] if fam else []
        return [("font-family", v if "," in v else "'%s',sans-serif" % v)]

    def props(self, kind, ident):
        out = {}
        for sel, plist in self.rules:
            if sel == "*" or sel == kind or (ident and sel == ident):
                for k, v in plist:
                    for pk, pv in self.decl(k, v, [], []):
                        out[pk] = pv
        return out

    def css(self):
        faces, imports, body = [], [], []
        for sel, plist in self.rules:
            decls = []
            for k, v in plist:
                decls += self.decl(k, v, faces, imports)
            if not decls:
                continue
            s = "body" if sel == "*" else '[data-id="%s"],.k-%s' % (sel, sel)
            body.append("%s{%s}" % (s, ";".join("%s:%s" % d for d in decls)))
        head = ["@import url('%s');" % u for u in imports]
        return "\n".join(head + faces + body)
