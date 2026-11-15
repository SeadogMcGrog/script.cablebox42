#!/usr/bin/env python3
"""Check the retro-ad data (resources/ads/ads.json):

  * nothing a kids' channel shows has a phone number (ads marked K: none, except a
    local spot's own number, which the card leaves off on kids' channels);
  * every phone number is 555-0100 to 555-0199 (with or without 1-800-/1-900-),
    and nothing else that looks like a phone number slips in;
  * ids are unique; formats, flavours, times, seasons and weather words are known;
  * kids' ads (flavour K) never have a 1-900 number or a contest;
  * every text a card shows is in strings.po (translations).

    python3 tools/retro-ads/check_ads.py [ads.json]

Exits 1 and lists the problems if anything is wrong.  No Kodi needed.
"""
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "resources", "ads", "ads.json")
PO = os.path.join(REPO, "resources", "language", "resource.language.en_gb", "strings.po")

FORMATS = {"pitch", "kids", "local", "psa", "video", "infomercial", "contest", "classifieds"}
FLAVOURS = {"G", "K", "S", "M", "L"}
TIMES = {"morn", "day", "prime", "late"}
SEASONS = {"holiday", "winter", "newyear", "spring", "summer", "school", "fall", "halloween"}
WEATHER = {"cold", "hot", "rain", "snow"}
TEXT_FIELDS = ("head", "sub", "claim", "label", "price", "cta", "small", "banner", "tagline", "where",
               "message", "second", "from")
# Not looked up in strings.po: brand names / phone numbers stay as they are
PLAIN_FIELDS = ("phone",)

PHONE = re.compile(r"(\d{3})-(\d{4})")
DIGITS = re.compile(r"\d{3}[-. ]?\d{4}")


def strings():
    out = set()
    with open(PO, encoding="utf-8") as f:
        for line in f:
            if line.startswith('msgid "'):
                out.add(json.loads(line[6:].strip()))
    return out


def texts(ad):
    """(field, text) of everything a card shows."""
    for k in TEXT_FIELDS:
        v = ad.get(k)
        if v:
            yield k, v
    for k in ("name", "seal"):
        for v in ad.get(k) or []:
            if v:
                yield k, v
    for k in PLAIN_FIELDS:
        if ad.get(k):
            yield k, ad[k]


def all_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from all_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_strings(v)


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    po = strings()
    bad = []
    ids = set()
    phones = 0
    for ad in data.get("ads", []):
        aid = ad.get("id", "?")
        if aid in ids:
            bad.append("%s: id used twice" % aid)
        ids.add(aid)
        if ad.get("fmt") not in FORMATS:
            bad.append("%s: unknown format %r" % (aid, ad.get("fmt")))
        for key, known in (("flav", FLAVOURS), ("time", TIMES), ("season", SEASONS),
                           ("weather", WEATHER), ("not_weather", WEATHER)):
            for v in ad.get(key) or []:
                if v not in known:
                    bad.append("%s: unknown %s %r" % (aid, key, v))
        if not ad.get("flav"):
            bad.append("%s: no flavour" % aid)
        kids = "K" in (ad.get("flav") or [])
        if kids and ad.get("fmt") in ("contest", "infomercial"):
            bad.append("%s: kids' ads can't be %s" % (aid, ad["fmt"]))
        for field, text in texts(ad):
            if field not in PLAIN_FIELDS and text not in po:
                bad.append("%s: not in strings.po: %r" % (aid, text))
            if kids and "1-900" in text:
                bad.append("%s: 1-900 number on a kids' ad" % aid)
            if kids and field != "phone" and DIGITS.search(text) and PHONE.fullmatch(DIGITS.search(text).group(0)):
                bad.append("%s: a phone number in %s on a kids' ad" % (aid, field))
        if kids and ad.get("phone") and ad.get("fmt") != "local":
            bad.append("%s: kids' ads have no phone number (only a local spot's, left off on kids' channels)" % aid)
        if kids and "%s" in (ad.get("cta") or ""):
            bad.append("%s: a kids' ad's call to action can't name a number" % aid)
    # every phone number anywhere in the file, ads or not
    for text in all_strings(data):
        for m in DIGITS.finditer(text):
            num = PHONE.fullmatch(m.group(0))
            if not num or num.group(1) != "555" or not (100 <= int(num.group(2)) <= 199):
                bad.append("phone number outside 555-0100..0199: %r in %r" % (m.group(0), text))
            else:
                phones += 1
        for m in re.finditer(r"1-(\d{3})-", text):
            if m.group(1) not in ("800", "900"):
                bad.append("phone prefix other than 1-800-/1-900-: %r" % text)
    for lines in (data.get("video") or {}).values():
        if isinstance(lines, list):
            for v in all_strings(lines):
                if v not in po and v not in ("G", "M"):
                    bad.append("video: not in strings.po: %r" % v)
    for b in bad:
        print("FAIL", b)
    print("%d ads, %d phone numbers checked: %s" % (len(ids), phones, "FAIL" if bad else "PASS"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
