#!/usr/bin/env python3
"""Build GS1's glossary by reusing every golden-sun-the-lost-age glossary
term that provably appears in GS1's own decoded text, so proper nouns
(character/place names) and shared system vocabulary stay identical across
both games -- important because both use phonetic transliteration, and a
diverging spelling would break continuity for a player going GS1 -> GS2.

Matches are exact-substring; short/common kana strings can false-positive
inside unrelated compound words (e.g. "シン" inside "アサッシンソード" / Assassin Sword).
Every match was manually reviewed against its GS1 context before inclusion;
see research/jp-codepage-derivation.md sibling note for the excluded list.
"""
import json

EXCLUDED_FALSE_POSITIVES = {
    "シン",     # only hits are inside アサッシン/ダンシング -- character not confirmed present in GS1
    "スサ",     # only hit is inside デスサイズ (Death Scythe) -- not confirmed present in GS1
    "サンド",   # only hit is inside サンドイッチ (sandwich) -- not the psynergy
    "まの海",   # only hit is いまの海 (今の海, "the sea right now") -- not 魔の海
}

# golden-sun-the-lost-age's glossary notes are written from GS2's own point of
# view ("前作" = the prior installment = GS1, "本作" = this installment = GS2).
# Copied verbatim into GS1's own glossary those pronouns point the wrong way,
# so entries whose notes depend on that framing get rewritten here to name the
# game explicitly instead of "前作"/"本作".
NOTE_OVERRIDES = {
    "サテュロス": "依日文名稱音譯；已於本作（第一部）原文核實出現",
    "ヨデム": "依日文名稱音譯；已於本作（第一部）原文核實出現",
    "トレビ": "城邦與戰士所屬地；依日文名稱音譯",
    "メナーディ": "依日文名稱音譯；已於本作（第一部）原文核實出現",
    "ガラハド": "托雷比競技場戰士（在《失落的時代》中為尋找本作主角並傳遞警告的角色）；依日文名稱音譯",
    "サトレージ": "托雷比競技場戰士；依英語版 Satrage 音譯",
    "アザート": "托雷比競技場戰士；依英語版 Azart 音譯",
    "ナヴァンバ": "托雷比競技場戰士；依英語版 Navampa 音譯",
    "アンガラ大陸": "海迪亞村與阿爾法山所在的大陸；依日文名稱音譯",
    "ハイディア村": "阿爾法山腳、本作主角出生的村落；依日文名稱音譯",
    "ルンパ": "漂流至雷姆利亞的傳奇盜賊，也是倫帕村建立者；依既有譯名慣例",
    "モルガン": "托雷比競技場第一戰士；依日文名稱音譯",
    "デッカ": "托雷比競技場第五戰士；依日文名稱音譯",
    "コウラン": "受本作主角幫助、為尋找恩人而旅行的烏魯木齊少女；採中文姓名形式",
    "クープアップ": "盜賊事件所在村落；依日文名稱音譯",
    "ロビン": "本作（第一部）地元素使主角；依既有劇情翻譯統一",
    "ジェラルド": "本作（第一部）火元素使夥伴；依既有劇情翻譯統一",
    "イワン": "本作（第一部）風元素使夥伴；依既有劇情翻譯統一",
    "メアリィ": "本作（第一部）水元素使夥伴；依系列英語名 Mia 音譯",
    "ガルシア": "《失落的時代》地元素使主角，本作（第一部）中為維納斯燈塔序章可操作角色；依既有劇情翻譯統一",
    "ジャスミン": "《失落的時代》火元素使夥伴，本作（第一部）中為維納斯燈塔序章可操作角色；依既有劇情翻譯統一",
    "シバ": "《失落的時代》風元素使夥伴，本作（第一部）中為維納斯燈塔序章可操作角色；依既有劇情翻譯統一",
}

gs2_terms = []
with open("../golden-sun-the-lost-age/translations/glossary.zh-TW.tsv", encoding="utf-8") as f:
    header = next(f)
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue
        ja, zh_tw, category, status, notes = parts
        gs2_terms.append((ja, zh_tw, category, notes))

gs1_texts = [json.loads(line)["text"] for line in open("research/jp-decoded.jsonl", encoding="utf-8")]

rows = []
for ja, zh_tw, category, notes in gs2_terms:
    if ja in EXCLUDED_FALSE_POSITIVES:
        continue
    if any(ja in text for text in gs1_texts):
        base_notes = NOTE_OVERRIDES.get(ja, notes)
        new_notes = base_notes + "；第一部原文同見，沿用《失落的時代》譯名以維持系列人名地名一致"
        rows.append((ja, zh_tw, category, "provisional", new_notes))

with open("translations/glossary.zh-TW.tsv", "w", encoding="utf-8") as out:
    out.write(header)
    for row in rows:
        out.write("\t".join(row) + "\n")

print(f"wrote {len(rows)} shared terms to translations/glossary.zh-TW.tsv")
