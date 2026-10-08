"""Build i18n/<lang>/LC_MESSAGES/ok.po + ok.mo from the workbooks in this folder.

Game words come from souseha BD2DB (names.json, terms.md).  Needs polib and
opencc.
"""

import json
import os
import re
import sys

import polib
from opencc import OpenCC

SP = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(SP, "..", ".."))
names = json.load(open(f"{SP}/names.json", encoding="utf-8"))
ui_keys = json.load(open(f"{SP}/ui_keys.json", encoding="utf-8"))
extra = json.load(open(f"{SP}/extra.json", encoding="utf-8"))  # {zh: {en,ja,ko}}
TW_TERMS = json.load(open(f"{SP}/tw_terms.json", encoding="utf-8"))  # {cn: tw}
cc = OpenCC("s2twp")


def to_tw(text):
    """OpenCC, but souseha's Traditional names for game terms."""
    table = dict(TW_TERMS)
    for cn, d in names.items():
        if d.get("tw"):
            table[cn] = d["tw"]
    marks = {}
    for i, cn in enumerate(sorted(table, key=len, reverse=True)):
        if cn in text:
            mark = f"{i}"
            text = text.replace(cn, mark)
            marks[mark] = table[cn]
    text = cc.convert(text)
    for mark, tw in marks.items():
        text = text.replace(mark, tw)
    return text


def placeholders(s):
    return sorted(re.findall(r"\{[a-z]+\}", s))


def write(lang, entries, merge_existing=False):
    folder = f"{REPO}/i18n/{lang}/LC_MESSAGES"
    os.makedirs(folder, exist_ok=True)
    path = f"{folder}/ok.po"
    if merge_existing and os.path.exists(path):
        po = polib.pofile(path)
    else:
        po = polib.POFile()
        po.metadata = {
            "Project-Id-Version": "ok-bd2 1.0",
            "Language": lang,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
        }
    existing = {e.msgid: e for e in po}
    for msgid, msgstr in sorted(entries.items()):
        if not msgstr:
            continue
        assert placeholders(msgid) == placeholders(msgstr), (lang, msgid, msgstr)
        if msgid in existing:
            existing[msgid].msgstr = msgstr
        else:
            po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    po.wrapwidth = 999999
    po.save(path)
    import subprocess

    subprocess.run(
        [sys.executable, f"{REPO}/scripts/compile_translations.py", path, f"{folder}/ok.mo"],
        check=True,
    )
    print(lang, len(po))


for lang, code in (("en", "en_US"), ("ja", "ja_JP"), ("ko", "ko_KR")):
    book = json.load(open(f"{SP}/ui_{lang}.json", encoding="utf-8"))["translations"]
    missing = [k for k in ui_keys if k not in book]
    assert not missing, (lang, missing[:5])
    entries = {k: book[k] for k in ui_keys}
    for cn, d in names.items():
        entries[cn] = d[lang]
    for zh, d in extra.items():
        entries[zh] = d[lang]
    write(code, entries, merge_existing=(code == "en_US"))

tw = {}
for k in list(ui_keys) + list(names) + list(extra):
    converted = to_tw(k)
    if converted != cc.convert(k):
        tw[k] = converted
write("zh_TW", tw)
