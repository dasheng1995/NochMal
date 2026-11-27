"""Lookup Chinese glosses from local Dehelper dictionary (combined.bin).

Usage:
  python dehelper_lookup.py Rücken
  python dehelper_lookup.py --lemma "der Rücken, -" --pos der
  python dehelper_lookup.py --batch lemmas.txt
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DIC = Path(r"E:\deutsch\Dehelper\dic\combined.bin")

ARTICLE_POS = {"der", "die", "das", "n", "noun", "sub", "m", "f", "nt"}
VERB_POS = {"verb", "v", "vt", "vi"}
ADJ_POS = {"adj", "adjektiv"}
ADV_POS = {"adv", "adverb"}

# Compound / noise prefixes before a false "Motor" head (Doppel-V-Motor, Acro-Motor…)
_BAD_PREV = set(b"-/_.\\:+#@")

# Gloss that looks like a real dictionary sense, not a product/city fragment.
_STYLED_GLOSS = re.compile(
    r"^(?:(?:refl\.|unpers\.)\s*)?(?:[mnfMNF]\.|pl\.|Vt\.|Vi\.|vt\.|vi\.|"
    r"Adj\.|adj\.|Adv\.|adv\.|Präp\.|Konj\.|Pron\.|Art\.|Num\.)"
)
_PLACE_JUNK = re.compile(
    r"(市|省|有限公司|股份有限|集团有限|电机厂|电话|网址|https?://|www\.|@.+\.)",
    re.I,
)
_LATIN_HEAVY = re.compile(r"[A-Za-z]{4,}")


def clean_lemma(lemma: str) -> str:
    s = (lemma or "").strip()
    s = re.sub(r"^(der|die|das)\s+", "", s, flags=re.I)
    s = s.split(",")[0].strip()
    s = re.sub(r"\s*\(.*\)$", "", s)
    if "," in s and re.search(r"[a-zäöüß]\s*,\s*[a-zäöüß]", s, re.I):
        s = s.split(",")[0].strip()
    return s


def detect_want(lemma: str, pos: str) -> str:
    """Return want bucket: noun|verb|adj|adv|any."""
    p = (pos or "").strip().lower()
    raw = (lemma or "").strip()
    if raw.lower().startswith(("der ", "die ", "das ")) or p in ARTICLE_POS:
        return "noun"
    if p in VERB_POS or re.match(r"^[a-zäöüß]+,\s*[a-zäöüß]+,", raw):
        return "verb"
    if p in ADJ_POS:
        return "adj"
    if p in ADV_POS:
        return "adv"
    return "any"


def gloss_kind(g: str) -> str:
    g = g.strip()
    g = re.sub(r"^(?:refl\.|unpers\.)\s*", "", g, flags=re.I)
    if re.match(r"^(?:[mnfMNF]\.|pl\.)", g):
        return "noun"
    if re.match(r"^(?:Vt\.|Vi\.|vt\.|vi\.)", g):
        return "verb"
    # "refl. vi. vt. …" after stripping refl still may start with vi/vt
    if re.match(r"^(?:vi\.|vt\.|Vi\.|Vt\.)(?:\s+(?:vi\.|vt\.|Vi\.|Vt\.))*", g):
        return "verb"
    if re.match(r"^(?:Adj\.|adj\.)", g):
        return "adj"
    if re.match(r"^(?:Adv\.|adv\.)", g):
        return "adv"
    if re.match(r"^(?:Präp\.|Konj\.|Pron\.|Art\.|Num\.)", g):
        return "other"
    return "plain"


def short_zh(g: str) -> str:
    """Strip dictionary POS prefix for quiz button text."""
    s = re.sub(
        r"^(?:(?:refl\.|unpers\.)\s*)?(?:[mnfMNF]\.|Vt\.|Vi\.|vt\.|vi\.|Adj\.|Adv\.|adj\.|adv\.|"
        r"Präp\.|Konj\.|Pron\.|Art\.|pl\.)(?:\s+(?:Vt\.|Vi\.|vt\.|vi\.))*\s*",
        "",
        g.strip(),
        flags=re.I,
    )
    s = re.split(r"[;；]", s)[0].strip()
    s = re.sub(r"\s+", "", s)
    if len(s) > 24:
        s = s[:24]
    return s


def _is_head_boundary(data: bytes, i: int) -> bool:
    """True if data[i] starts an independent headword, not a compound tail."""
    if i < 0:
        return False
    prev = data[i - 1] if i > 0 else 0
    # mid-latin word
    if (65 <= prev <= 90) or (97 <= prev <= 122):
        return False
    # mid UTF-8 of longer German word
    if prev >= 0x80:
        return False
    # compound joiners: Doppel-V-Motor, Acro/Motor, foo_Motor
    if prev in _BAD_PREV:
        return False
    # digit-compound tails (2Motor) rare but reject
    if 48 <= prev <= 57:
        return False
    return True


def _gloss_quality(gloss: str) -> int:
    """Higher = likelier a real dictionary sense."""
    g = (gloss or "").strip()
    if not g:
        return -10
    score = 0
    if _STYLED_GLOSS.match(g):
        score += 6
    if _PLACE_JUNK.search(g):
        score -= 8
    # Broken fragments like 的DraI燃料发动机
    if re.match(r"^[的地得]", g) and _LATIN_HEAVY.search(g):
        score -= 6
    latin = len(_LATIN_HEAVY.findall(g))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", g))
    if latin >= 2 and cjk <= 6:
        score -= 4
    if cjk >= 2:
        score += 1
    if cjk >= 4:
        score += 1
    return score


def _pick_gloss(parts: list[bytes]) -> str | None:
    """Prefer styled POS gloss among nearby null-separated fields."""
    decoded: list[str] = []
    for p in parts[:10]:
        if not p or len(p) > 400:
            continue
        try:
            s = p.decode("utf-8")
        except UnicodeDecodeError:
            continue
        s = s.strip()
        if not re.search(r"[\u4e00-\u9fff]", s) or s.startswith("<"):
            continue
        decoded.append(s)
    if not decoded:
        return None
    # Prefer m./Vt./Adj. style over bare plain junk
    ranked = sorted(decoded, key=_gloss_quality, reverse=True)
    best = ranked[0]
    if _gloss_quality(best) < 0 and not _STYLED_GLOSS.match(best):
        # still return nearest if everything looks bad — caller may filter
        return decoded[0]
    return best


def _extract_near(data: bytes, pos: int, head: str) -> dict | None:
    start = pos + len(head.encode("utf-8"))
    if start >= len(data) or data[start] != 0:
        return None
    window = data[start + 1 : start + 1 + 320]
    parts = window.split(b"\x00")
    gloss = _pick_gloss(parts)
    if not gloss:
        return None
    text = window.decode("utf-8", "replace")
    pos_tag = ""
    pm = re.search(r"<pos>([^<]+)</pos>", text)
    if pm:
        pos_tag = pm.group(1).strip()
    # Headword entry often has <pl>Motor…</pl><pos>m.</pos> right after
    has_pl = bool(re.search(rf"<pl>\s*{re.escape(head)}", text, flags=re.I))
    has_pos_xml = bool(pos_tag)
    return {
        "lemma": head,
        "def_zh": gloss,
        "def_zh_short": short_zh(gloss),
        "pos_tag": pos_tag,
        "kind": gloss_kind(gloss),
        "offset": pos,
        "case_exact": True,
        "has_pl": has_pl,
        "has_pos_xml": has_pos_xml,
        "q": _gloss_quality(gloss),
    }


def lookup(
    word: str,
    data: bytes | None = None,
    pos: str = "",
) -> list[dict]:
    if data is None:
        data = DIC.read_bytes()
    head = clean_lemma(word)
    if not head:
        return []
    want = detect_want(word, pos)

    variants: list[bytes] = []
    for v in (
        head.encode("utf-8"),
        (head[:1].upper() + head[1:]).encode("utf-8") if head else b"",
        head.lower().encode("utf-8"),
        head.capitalize().encode("utf-8"),
    ):
        if v and v not in variants:
            variants.append(v)

    hits: list[dict] = []
    seen_off: set[int] = set()
    # Scan more candidates so true head (often later in file) is not missed.
    per_variant_cap = 64
    for var in variants:
        start = 0
        found_here = 0
        while found_here < per_variant_cap:
            i = data.find(var, start)
            if i < 0:
                break
            start = i + 1
            end = i + len(var)
            if end >= len(data) or data[end] != 0:
                continue
            if not _is_head_boundary(data, i):
                continue
            if i in seen_off:
                continue
            seen_off.add(i)
            got = _extract_near(data, i, var.decode("utf-8"))
            if not got:
                continue
            # Drop obvious junk unless nothing else (filtered later by score)
            # Only drop clear junk (place/company noise); keep weak-but-real glosses.
            if got["q"] <= -7 and not got.get("has_pl") and got["kind"] == "plain":
                continue
            got["case_exact"] = var.decode("utf-8") == head or (
                want == "noun" and var.decode("utf-8") == (head[:1].upper() + head[1:])
            )
            hits.append(got)
            found_here += 1

    def score(h: dict) -> tuple:
        kind = h["kind"]
        kind_match = 0
        if want == "any":
            kind_match = 1
        elif want == kind:
            kind_match = 5
        elif want == "noun" and kind == "plain":
            kind_match = 1
        elif want == "verb" and kind == "plain":
            kind_match = 1
        elif want == "adj" and kind == "plain":
            kind_match = 1
        elif want == "noun" and kind == "verb":
            kind_match = -2
        elif want == "verb" and kind == "noun":
            kind_match = -2

        styled = 2 if kind != "plain" else 0
        case_sc = 2 if h.get("case_exact") else 0
        if want == "noun" and h["lemma"][:1].isupper():
            case_sc += 1
        if want == "verb" and h["lemma"][:1].islower():
            case_sc += 1

        struct = 0
        if h.get("has_pl"):
            struct += 4
        if h.get("has_pos_xml"):
            struct += 2
        # XML pos agreeing with want
        xml = (h.get("pos_tag") or "").lower()
        if want == "noun" and xml in {"m.", "f.", "n.", "m", "f", "n"}:
            struct += 3
        if want == "verb" and "v" in xml:
            struct += 3
        if want == "adj" and "adj" in xml:
            struct += 3

        q = int(h.get("q") or 0)
        cjk = len(re.findall(r"[\u4e00-\u9fff]", h["def_zh"]))
        return (kind_match, struct, styled, q, case_sc, cjk)

    hits.sort(key=score, reverse=True)
    uniq = []
    seen = set()
    for h in hits:
        k = h["def_zh"]
        if k in seen:
            continue
        seen.add(k)
        uniq.append(h)
    return uniq


def best_zh(word: str, data: bytes | None = None, pos: str = "") -> str:
    hits = lookup(word, data=data, pos=pos)
    if not hits:
        return ""
    return hits[0]["def_zh_short"] or hits[0]["def_zh"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("word", nargs="?")
    ap.add_argument("--lemma", default="")
    ap.add_argument("--pos", default="")
    ap.add_argument("--batch", type=Path)
    ap.add_argument("--json-out", type=Path)
    args = ap.parse_args()
    if not DIC.exists():
        raise SystemExit(f"missing dictionary: {DIC}")
    data = DIC.read_bytes()

    if args.batch:
        rows = []
        for ln in args.batch.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            if "\t" in ln:
                lemma, pos = ln.split("\t", 1)
            else:
                lemma, pos = ln, ""
            hits = lookup(lemma, data, pos=pos)
            rows.append(
                {
                    "lemma": lemma,
                    "pos": pos,
                    "best": hits[0]["def_zh_short"] if hits else "",
                    "best_full": hits[0]["def_zh"] if hits else "",
                    "hits": hits[:3],
                }
            )
            print(f"{lemma}\t{rows[-1]['best'] or 'NOT FOUND'}")
        if args.json_out:
            args.json_out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    word = args.lemma or args.word
    if not word:
        raise SystemExit("provide word")
    hits = lookup(word, data, pos=args.pos)
    if hits:
        print(f"{word} -> {hits[0]['def_zh_short']}  << {hits[0]['def_zh']}")
        for h in hits[1:4]:
            print(f"  alt: {h['def_zh_short']}  << {h['def_zh']}")
    else:
        print(f"{word} -> NOT FOUND")


if __name__ == "__main__":
    main()
