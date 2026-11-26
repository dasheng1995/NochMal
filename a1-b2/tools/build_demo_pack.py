"""Build a 100-word A1 demo .deword pack with meaning images + bilingual glosses."""
from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import sqlite3
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"e:\local_project\deutsch\a1-b2")
EXTRACT = ROOT / "_apkg_extract"
DB = EXTRACT / "collection_decomp.anki2"
OUT_DIR = ROOT / "packs"
WORK = ROOT / "_demo_pack_work"
PACK_NAME = "demo_a1_100.deword"
LIMIT = 100
MAIN_NT = 1776081424953
SEP = "\x1f"

# EN gloss -> ZH for definitions / short phrases
ZH_GLOSS = {
    "the": "这/那（定冠词）",
    "and": "和，并且",
    "in": "在…里",
    "I": "我",
    "you": "你",
    "it": "它",
    "is": "是",
    "to be": "是，存在",
    "have": "有",
    "to have": "有",
    "not": "不",
    "that": "那，那个",
    "a": "一个（不定冠词）",
    "for": "为了，对于",
    "on": "在…上",
    "with": "和…一起；用",
    "he": "他",
    "she": "她",
    "we": "我们",
    "they": "他们",
    "this": "这个",
    "from": "从，来自",
    "at": "在",
    "by": "被；通过",
    "or": "或者",
    "as": "作为；如同",
    "but": "但是",
    "what": "什么",
    "all": "全部",
    "can": "能，可以",
    "to can / be able": "能，会",
    "will": "将，会",
    "if": "如果",
    "about": "关于",
    "who": "谁",
    "get": "得到",
    "to get": "得到；到达",
    "which": "哪个",
    "go": "去",
    "to go": "去",
    "me": "我（宾格）",
    "when": "当…时",
    "make": "做；使",
    "to make": "做；制作",
    "like": "像；喜欢",
    "time": "时间",
    "no": "不；没有",
    "no, not a": "不；没有一个",
    "just": "刚刚；只是",
    "him": "他（宾格）",
    "know": "知道",
    "to know": "知道",
    "take": "拿；带",
    "to take": "拿；花费",
    "people": "人们",
    "into": "进入",
    "year": "年",
    "your": "你的",
    "good": "好的",
    "some": "一些",
    "could": "可能；可以",
    "them": "他们（宾格）",
    "see": "看见",
    "to see": "看见",
    "other": "其他的",
    "than": "比",
    "then": "然后",
    "now": "现在",
    "look": "看",
    "to look": "看",
    "only": "仅仅",
    "come": "来",
    "to come": "来",
    "its": "它的",
    "over": "在…上方；结束",
    "think": "想",
    "to think": "想；认为",
    "also": "也",
    "back": "回；背面",
    "after": "在…之后",
    "use": "使用",
    "to use": "使用",
    "two": "二",
    "how": "怎样",
    "our": "我们的",
    "work": "工作",
    "to work": "工作",
    "first": "第一",
    "well": "好地；井",
    "way": "路；方式",
    "even": "甚至",
    "new": "新的",
    "want": "想要",
    "to want": "想要",
    "because": "因为",
    "any": "任何",
    "these": "这些",
    "give": "给",
    "to give": "给",
    "day": "天；日",
    "most": "大多数",
    "us": "我们（宾格）",
    "more": "更多",
    "yes": "是的",
    "here": "这里",
    "there": "那里",
    "where": "哪里",
    "why": "为什么",
    "say": "说",
    "to say": "说",
    "my": "我的",
    "his": "他的",
    "her": "她的",
    "one": "一；一个",
    "man": "男人",
    "woman": "女人",
    "child": "孩子",
    "house": "房子",
    "water": "水",
    "hand": "手",
    "eye": "眼睛",
    "head": "头",
    "door": "门",
    "table": "桌子",
    "chair": "椅子",
    "book": "书",
    "school": "学校",
    "friend": "朋友",
    "city": "城市",
    "car": "汽车",
    "food": "食物",
    "bread": "面包",
    "apple": "苹果",
    "tree": "树",
    "sun": "太阳",
    "moon": "月亮",
    "night": "夜晚",
    "morning": "早晨",
    "evening": "晚上",
    "father": "父亲",
    "mother": "母亲",
    "brother": "兄弟",
    "sister": "姐妹",
    "family": "家庭",
    "name": "名字",
    "question": "问题",
    "answer": "回答",
    "to answer": "回答",
    "to ask": "问",
    "to live": "住；生活",
    "to speak": "说；讲",
    "to hear": "听见",
    "to write": "写",
    "to read": "读",
    "to eat": "吃",
    "to drink": "喝",
    "to sleep": "睡",
    "to buy": "买",
    "to sell": "卖",
    "to help": "帮助",
    "to play": "玩；演奏",
    "to learn": "学习",
    "to teach": "教",
    "big": "大的",
    "small": "小的",
    "old": "老的；旧的",
    "young": "年轻的",
    "beautiful": "美丽的",
    "bad": "坏的",
    "right": "对的；右边",
    "left": "左边",
    "long": "长的",
    "short": "短的",
    "high": "高的",
    "low": "低的",
    "hot": "热的",
    "cold": "冷的",
    "red": "红色的",
    "blue": "蓝色的",
    "green": "绿色的",
    "white": "白色的",
    "black": "黑色的",
    "no, none": "不；没有",
    "not a / no": "不；没有",
}

# lemma/keyword hints for image search (meaning scene, not the spelling)
LEMMA_IMAGE_QUERY = {
    "der": "man male person",
    "die": "woman female person",
    "das": "child object thing",
    "kein": "empty none zero forbidden",
    "eine": "one apple single",
    "ein": "one object single",
    "und": "together handshake friends",
    "in": "inside room box",
    "ich": "person selfie portrait",
    "du": "person pointing you",
    "sie": "people group",
    "ist": "checkmark yes",
    "nicht": "no stop forbidden red",
    "auch": "plus also add",
    "auf": "on top table",
    "für": "gift for present",
    "mit": "together friends",
    "es": "it object",
    "zu": "to door path",
    "den": "man pointing",
    "haben": "have hold hands",
    "sein": "to be existence",
    "werden": "growth change plant",
    "können": "ability strength can",
    "müssen": "must duty clock",
    "sagen": "talk speak conversation",
    "machen": "make craft hands",
    "geben": "give gift hand",
    "kommen": "arrive door welcome",
    "gehen": "walk path street",
    "sehen": "eye look see",
    "wissen": "knowledge book brain",
    "wollen": "want desire wish",
    "mehr": "more pile increase",
    "schon": "already clock time",
    "noch": "still continue",
    "nur": "only one single",
    "oder": "or choice fork",
    "aber": "but contrast",
    "wenn": "if weather rain umbrella",
    "weil": "because reason why",
    "hier": "here location pin",
    "da": "there place map",
    "wo": "where map location",
    "was": "what question mark",
    "wer": "who person question",
    "wie": "how question",
    "ja": "yes thumbs up",
    "nein": "no thumbs down",
    "bitte": "please thank you polite",
    "danke": "thank you gratitude",
    "hallo": "hello wave greeting",
    "gut": "good thumbs up",
    "heute": "today calendar sun",
    "morgen": "morning sunrise",
    "Abend": "evening sunset",
    "Zeit": "time clock watch",
    "Jahr": "year calendar",
    "Tag": "day sun calendar",
    "Haus": "house home building",
    "Tisch": "wooden table furniture",
    "Stuhl": "chair furniture",
    "Buch": "book reading",
    "Schule": "school building",
    "Freund": "friends friendship",
    "Stadt": "city skyline",
    "Auto": "car automobile",
    "Wasser": "water glass",
    "Brot": "bread bakery",
    "Apfel": "red apple fruit",
    "Baum": "tree forest",
    "Kind": "child kid",
    "Mann": "man person",
    "Frau": "woman person",
    "Tür": "door entrance",
    "Fenster": "window house",
    "Hand": "hand human",
}


def field_map(conn: sqlite3.Connection) -> dict[int, str]:
    return {
        ord_: name
        for ntid, ord_, name in conn.execute(
            "SELECT ntid, ord, name FROM fields WHERE ntid=? ORDER BY ord",
            (MAIN_NT,),
        )
    }


def sound_name(field: str) -> str | None:
    m = re.search(r"\[sound:([^\]]+)\]", field or "")
    return m.group(1) if m else None


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    val = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7


def load_media_map() -> dict[str, str]:
    import zstandard as zstd

    media_path = EXTRACT / "media"
    raw = media_path.read_bytes()
    meta = zstd.ZstdDecompressor().decompress(raw, max_output_size=50_000_000)
    entries: list[str] = []
    i = 0
    while i < len(meta):
        if meta[i] != 0x0A:
            i += 1
            continue
        i += 1
        length, i = _read_varint(meta, i)
        msg = meta[i : i + length]
        i += length
        j = 0
        name = None
        while j < len(msg):
            key = msg[j]
            j += 1
            fn, wt = key >> 3, key & 7
            if wt == 2:
                l, j = _read_varint(msg, j)
                val = msg[j : j + l]
                j += l
                if fn == 1:
                    name = val.decode("utf-8", "replace")
            elif wt == 0:
                _, j = _read_varint(msg, j)
            else:
                break
        if name:
            entries.append(name)
    return {name: str(idx) for idx, name in enumerate(entries)}


def read_media_bytes(numeric_id: str) -> bytes | None:
    import zstandard as zstd

    src = EXTRACT / str(numeric_id)
    if not src.exists():
        return None
    data = src.read_bytes()
    if data[:4] == b"\x28\xb5\x2f\xfd":
        data = zstd.ZstdDecompressor().decompress(data, max_output_size=20_000_000)
    return data


def copy_audio(media_map: dict[str, str], filename: str, dest: Path) -> bool:
    if not filename:
        return False
    key = media_map.get(filename)
    if key is None:
        for k, v in media_map.items():
            if k.startswith(filename.rstrip(".")) or filename.startswith(k[:40]):
                key = v
                break
    if key is None:
        return False
    data = read_media_bytes(key)
    if not data:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return True


def zh_of(en: str) -> str:
    en = (en or "").strip()
    if not en:
        return ""
    if en in ZH_GLOSS:
        return ZH_GLOSS[en]
    low = en.lower()
    for k, v in ZH_GLOSS.items():
        if k.lower() == low:
            return v
    # try first clause
    first = re.split(r"[,;/]", en)[0].strip()
    for k, v in ZH_GLOSS.items():
        if k.lower() == first.lower():
            return v
    return first  # temporary; may be replaced by translator


def clean_lemma(lemma: str) -> str:
    # "der Tisch, -e" -> "Tisch"
    s = lemma.strip()
    s = re.sub(r"^(der|die|das)\s+", "", s, flags=re.I)
    s = s.split(",")[0].strip()
    s = re.sub(r"\s*\(.*\)$", "", s)
    return s


def image_query(lemma: str, def_en: str) -> str:
    base = clean_lemma(lemma)
    if base in LEMMA_IMAGE_QUERY:
        return LEMMA_IMAGE_QUERY[base]
    # strip article forms
    for k, v in LEMMA_IMAGE_QUERY.items():
        if base.lower() == k.lower():
            return v
    # from English gloss keywords
    gloss = re.sub(r"^(to\s+)", "", def_en.strip(), flags=re.I)
    gloss = re.split(r"[,;/]", gloss)[0]
    words = re.findall(r"[A-Za-z]{3,}", gloss)
    if words:
        return " ".join(words[:3])
    return base or "object"


def download_meaning_image(query: str) -> Image.Image | None:
    """Fetch a meaning-related image (AI scene / web). Prefer fast endpoints."""
    prompt = f"simple clear photo illustrating: {query}, no text, no watermark, educational flashcard"
    urls = [
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + "?width=640&height=480&nologo=true&seed="
        + str(abs(hash(query)) % 100000),
    ]
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0 DeutschVocabDemo/1.0")]
    urllib.request.install_opener(opener)
    for url in urls:
        try:
            with urllib.request.urlopen(url, timeout=8) as resp:
                data = resp.read()
            if len(data) < 1000:
                continue
            img = Image.open(io.BytesIO(data)).convert("RGB")
            return img
        except Exception:
            continue
    return None


def make_fallback_scene(path: Path, def_zh: str, def_en: str, query: str) -> None:
    """Pictogram-style meaning card (no German lemma spelling as the hero)."""
    w, h = 640, 480
    digest = hashlib.md5(query.encode("utf-8")).hexdigest()
    bg = (230, 240, 250)
    accent = (
        60 + int(digest[0:2], 16) // 3,
        110 + int(digest[2:4], 16) // 4,
        180 + int(digest[4:6], 16) // 5,
    )
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    # abstract meaning icon block
    draw.rounded_rectangle((180, 60, 460, 280), radius=40, fill=accent)
    qlow = query.lower()
    if any(k in qlow for k in ("table", "tisch", "furniture")):
        draw.rectangle((220, 140, 420, 180), fill=(255, 255, 255))
        draw.rectangle((250, 180, 270, 250), fill=(255, 255, 255))
        draw.rectangle((370, 180, 390, 250), fill=(255, 255, 255))
    elif any(k in qlow for k in ("book", "buch", "read")):
        draw.rectangle((250, 100, 390, 250), fill=(255, 255, 255))
        draw.line((320, 100, 320, 250), fill=accent, width=4)
    elif any(k in qlow for k in ("house", "haus", "home")):
        draw.polygon([(320, 90), (220, 160), (420, 160)], fill=(255, 255, 255))
        draw.rectangle((250, 160, 390, 250), fill=(255, 255, 255))
    elif any(k in qlow for k in ("no", "none", "forbidden", "empty", "kein")):
        draw.ellipse((230, 100, 410, 260), outline=(220, 60, 60), width=14)
        draw.line((255, 125, 385, 235), fill=(220, 60, 60), width=14)
    elif any(k in qlow for k in ("walk", "go", "path", "kommen", "gehen")):
        draw.ellipse((290, 100, 350, 160), fill=(255, 255, 255))
        draw.line((320, 160, 320, 220), fill=(255, 255, 255), width=10)
        draw.line((320, 180, 280, 210), fill=(255, 255, 255), width=8)
        draw.line((320, 180, 360, 210), fill=(255, 255, 255), width=8)
    else:
        draw.ellipse((250, 110, 390, 250), fill=(255, 255, 255))

    try:
        font_b = ImageFont.truetype("msyh.ttc", 34)
        font_s = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font_b = ImageFont.load_default()
        font_s = font_b
    title = (def_zh or def_en or query)[:20]
    sub = (def_en or query)[:42]
    draw.text((40, 320), title, fill=(30, 30, 30), font=font_b)
    draw.text((40, 380), sub, fill=(90, 90, 90), font=font_s)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=42, method=6)


def save_meaning_image(path: Path, lemma: str, def_en: str, def_zh: str) -> str:
    query = image_query(lemma, def_en)
    img = download_meaning_image(query)
    path.parent.mkdir(parents=True, exist_ok=True)
    if img is not None:
        img = img.resize((640, 480), Image.Resampling.LANCZOS)
        img.save(path, "WEBP", quality=40, method=6)
        return query
    make_fallback_scene(path, def_zh, def_en, query)
    return query


def try_translator():
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="en", target="zh-CN")
    except Exception:
        return None


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"Missing DB: {DB}")

    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "audio").mkdir(parents=True)
    (WORK / "images").mkdir(parents=True)

    translator = try_translator()
    media_map = load_media_map()
    conn = sqlite3.connect(str(DB))
    fmap = field_map(conn)
    name_to_ord = {v: k for k, v in fmap.items()}

    words = []
    for nid, mid, tags, flds in conn.execute(
        "SELECT id, mid, tags, flds FROM notes WHERE mid=? ORDER BY id",
        (MAIN_NT,),
    ):
        parts = flds.split(SEP)

        def get(name: str) -> str:
            i = name_to_ord.get(name)
            if i is None or i >= len(parts):
                return ""
            return parts[i].strip()

        level = get("Level")
        if level != "A1":
            continue

        rank = get("Rank")
        lemma = get("Word")
        ipa = get("IPA")
        pos1 = get("Part-of-Speech 1")
        def_en = get("Definition 1")
        def_zh = zh_of(def_en)
        if translator and (not def_zh or def_zh == def_en or def_zh == re.split(r"[,;/]", def_en)[0].strip()):
            try:
                def_zh = translator.translate(def_en) or def_zh
            except Exception:
                pass

        ex_de = get("German 1")
        ex_en = get("English 1")
        ex_zh = ""
        if translator and ex_en:
            try:
                ex_zh = translator.translate(ex_en) or ""
            except Exception:
                ex_zh = ""
        if not ex_zh:
            ex_zh = zh_of(ex_en) if ex_en else ""

        word_audio = sound_name(get("WordAudio"))
        sent_audio = sound_name(get("SentenceAudio1"))

        wid = f"a1_{rank}_{nid}"
        img_rel = f"images/{wid}.webp"
        query = save_meaning_image(WORK / img_rel, lemma, def_en, def_zh)

        audio_word_rel = None
        if word_audio:
            dest = WORK / "audio" / f"{wid}_word.mp3"
            if copy_audio(media_map, word_audio, dest):
                audio_word_rel = f"audio/{wid}_word.mp3"

        audio_sent_rel = None
        if sent_audio:
            dest = WORK / "audio" / f"{wid}_s1.mp3"
            if copy_audio(media_map, sent_audio, dest):
                audio_sent_rel = f"audio/{wid}_s1.mp3"

        words.append(
            {
                "id": wid,
                "rank": int(float(rank)) if rank else len(words) + 1,
                "lemma": lemma,
                "ipa": ipa,
                "level": "A1",
                "pos": pos1,
                "def_en": def_en,
                "def_zh": def_zh,
                "example_de": ex_de,
                "example_en": ex_en,
                "example_zh": ex_zh or ex_en,
                "audio_word": audio_word_rel,
                "audio_sentence": audio_sent_rel,
                "image": {
                    "path": img_rel,
                    "source": "web",
                    "query_or_prompt": query,
                },
                "tags": tags.split(),
            }
        )
        print(f"[{len(words)}/{LIMIT}] {lemma} <- {query}")
        if len(words) >= LIMIT:
            break

    conn.close()
    if len(words) < LIMIT:
        raise SystemExit(f"Only found {len(words)} A1 words")

    words_path = WORK / "words.json"
    words_path.write_text(json.dumps(words, ensure_ascii=False, indent=2), encoding="utf-8")
    content_hash = hashlib.sha256(words_path.read_bytes()).hexdigest()[:16]
    manifest = {
        "format": "deword",
        "version": 2,
        "level": "A1",
        "pack_id": "demo_a1_100",
        "title": "Demo A1 100",
        "word_count": len(words),
        "content_hash": content_hash,
        "notes": "Meaning images via web search keywords; bilingual ZH/EN glosses & examples.",
    }
    (WORK / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pack = OUT_DIR / PACK_NAME
    if out_pack.exists():
        out_pack.unlink()
    with zipfile.ZipFile(out_pack, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in WORK.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(WORK).as_posix())
    print(f"Wrote {out_pack} ({out_pack.stat().st_size/1024/1024:.2f} MB)")


if __name__ == "__main__":
    main()
