"""Build file A (English image-search queries) for all 100 words in demo_a1_100."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

# Reuse heuristics + overrides from the 20-word builder
from build_image_query_file_a import VISUAL_OVERRIDE, build_query

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
SRC_PACK = ROOT / "packs" / "demo_a1_100.deword"
OUT_QUERIES = ROOT / "packs" / "image_search_queries_demo100.json"

# Extra hand-tuned queries for the remaining function words / hard cases.
EXTRA_OVERRIDE = {
    "als": ("B", "person arriving home dark evening", "conj when; example scene"),
    "dies": ("B", "person looking at favorite picture", "pronoun this; example scene"),
    "wie": ("B", "person checking wristwatch waiting", "pronoun how; example scene"),
    "wir": ("B", "couple with suitcase summer vacation", "pronoun we; example scene"),
    "ihr": ("B", "girl annoying her brother", "pronoun her; example scene"),
    "so": ("B", "person copying someone watching carefully", "adv thus; example scene"),
    "bei": ("B", "patient visiting doctor clinic", "prep at/with; example scene"),
    "sein": ("B", "boy annoying his sister", "possessive his; example scene"),
    "aber": ("B", "sunny cold weather outdoors", "conj but; example scene"),
    "man": ("B", "people telling stories together", "pronoun one/they; example scene"),
    "noch": ("B", "student asking questions classroom", "adv still; example scene"),
    "nach": ("B", "people walking in park after lunch", "prep after; example scene"),
    "oder": ("B", "bicycle and bus transportation choice", "conj or; example scene"),
    "all": ("B", "family packing excited for vacation", "pronoun all; example scene"),
    "aus": ("B", "person looking out the window", "prep out of; example scene"),
    "was": ("B", "two people talking conversation", "pronoun what; example scene"),
    "nur": ("B", "two euro coins small price", "adv only; example scene"),
    "dann": ("B", "shopping bags then restaurant dinner", "adv then; example scene"),
    "wenn": ("B", "two friends meeting and talking", "conj when/if; example scene"),
    "müssen, muss, musste, hat gemusst": ("A", "person checking clock hurrying home", "verb must; example scene"),
    "um": ("B", "children running around a tree", "prep around; example scene"),
    "ja": ("B", "person nodding yes understanding", "particle yes; example scene"),
    "kein": ("B", "sports team losing no chance", "pronoun no/none; example scene"),
    "über": ("B", "airplane flying above person", "prep above; example scene"),
    "da": ("B", "car parked over there street", "adv there; example scene"),
    "geben, gibt, gab, hat gegeben": ("A", "person giving books to seller", "verb give; example scene"),
    "vor": ("B", "woman waiting in front of door", "prep in front; example scene"),
    "mein": ("B", "little sister family portrait", "pronoun my; example scene"),
    "mehr": ("B", "hungry person wanting more bread", "adv more; example scene"),
    "das Jahr, -e": ("A", "calendar year weeks pages", "noun year"),
    "du": ("B", "two people meeting greeting who are you", "pronoun you; example scene"),
    "durch": ("B", "person walking through city street", "prep through; example scene"),
    "viel": ("B", "spending money shopping vacation", "pronoun much; example scene"),
    "wollen, will, wollte, hat gewollt": ("A", "children wanting to play outdoors", "verb want; example scene"),
    "machen, macht, machte, hat gemacht": ("A", "students doing homework tasks desk", "verb do/make; example scene"),
    "andere (r, s)": ("B", "another path road to train station", "pronoun other; example scene"),
    "sollen, soll, sollte, hat gesollt": ("A", "quiet library studying should be quiet", "verb should; example scene"),
    "schon": ("B", "worker long career office years", "adv already; example scene"),
    "kommen, kommt, kam, ist gekommen": ("A", "friends arriving visit evening home", "verb come; example scene"),
    "mir": ("B", "giving bicycle to someone", "pronoun me; example scene"),
    "immer": ("B", "breakfast bread every morning", "adv always; example scene"),
    "mich": ("B", "sitting next to someone at table", "pronoun me; example scene"),
    "gehen, geht, ging, ist gegangen": ("A", "people going to theater evening", "verb go; example scene"),
    "groß": ("B", "large apartment interior spacious", "adj big; example scene"),
    "hier": ("B", "bedroom room interior here", "adv here; example scene"),
    "zwei": ("B", "two sisters standing together", "num two; example scene"),
    "also": ("B", "new student classroom introduction", "adv so; example scene"),
    "jetzt": ("B", "going to bed now night", "adv now; example scene"),
    "doch": ("B", "sunny day staying home window", "adv however; example scene"),
    "uns": ("B", "friends visiting looking forward", "pronoun us; example scene"),
    "gut": ("B", "flowers smelling good garden", "adj good; example scene"),
    "bis": ("B", "mother working until seven clock", "prep until; example scene"),
    "wissen, weiß, wusste, hat gewusst": ("A", "student knowing answers school", "verb know; example scene"),
    "sehen, sieht, sah, hat gesehen": ("A", "person wearing new glasses seeing", "verb see; example scene"),
    "einer": ("B", "one problem of many checklist", "pronoun one; example scene"),
    "sehr": ("B", "very good doctor professional woman", "adv very; example scene"),
    "Mal": ("A", "dark mark spot on skin", "noun mark/time; example scene"),
    "neu": ("B", "new bag shopping replacement", "adj new; example scene"),
    "stehen, steht, stand, hat gestanden": ("A", "bicycles standing in cellar", "verb stand; example scene"),
    "unser": ("B", "sports club team lost game", "pronoun our; example scene"),
    "jede (r, s)": ("B", "family summer vacation every year", "pronoun every; example scene"),
    "weil": ("B", "mother early morning going to work", "conj because; example scene"),
    "unter": ("B", "river flowing under bridge", "prep under; example scene"),
    "der Mensch, -en": ("A", "crowd of people human beings world", "noun human"),
    "ihm": ("B", "handing apartment keys to him", "pronoun him; example scene"),
    "ihn": ("B", "meeting him at university campus", "pronoun him; example scene"),
    "denn": ("B", "closed shops on sunday street", "conj because; example scene"),
    "das Beispiel, -e": ("A", "textbook example illustration page", "noun example"),
    "erste (r, s)": ("B", "baby first birthday cake celebration", "adj first; example scene"),
    "die Zeit, -en": ("A", "person working on task with clock", "noun time"),
    "lang": ("B", "long legs running race track", "adj long; example scene"),
    "leben, lebt, lebte, hat gelebt": ("A", "elderly people living long life", "verb live; example scene"),
    "die Frau, -en": ("A", "women workplace equal pay", "noun woman"),
    "wenig": ("B", "few people small group trust", "adj few; example scene"),
    "finden, findet, fand, hat gefunden": ("A", "person searching finding bag", "verb find; example scene"),
    "gegen": ("B", "losing sports competition against rival", "prep against; example scene"),
    "zwischen": ("B", "bicycle standing between trees", "prep between; example scene"),
}


def main():
    # Merge overrides into shared map used by build_query
    VISUAL_OVERRIDE.update(EXTRA_OVERRIDE)

    with zipfile.ZipFile(SRC_PACK, "r") as zf:
        words = json.loads(zf.read("words.json").decode("utf-8"))

    queries = [build_query(w) for w in words]
    file_a = {
        "format": "image_search_queries",
        "version": 1,
        "pack_id": "demo_a1_100",
        "word_count": len(queries),
        "rules": {
            "branch_A": "noun/verb -> English gloss / progressive scene",
            "branch_B": "adj/adv/other -> 2-3 visual nouns from example",
            "sources": "Pixabay/Pexels (API key) -> Wikimedia fallback",
            "next_agent": "fill_demo100_images.py",
        },
        "items": queries,
    }
    OUT_QUERIES.write_text(json.dumps(file_a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_QUERIES} items={len(queries)}")
    for q in queries[:8]:
        print(f"  [{q['branch']}] {q['lemma_core'][:16]:16} -> {q['search_en']}")
    print("  ...")


if __name__ == "__main__":
    main()
