import re
import os

base = r"C:\Users\Usernom\Documents\Terramine\Memory\derived\ad_close\runs\20261116_173511"

PAT = re.compile(r"close|dismiss|skip|adchoice|ad_choice|adchoices", re.I)

for n in ["poll_01.xml", "poll_05.xml", "poll_09.xml", "poll_11.xml", "poll_13.xml"]:
    p = os.path.join(base, n)
    if not os.path.exists(p):
        continue
    s = open(p, encoding="utf-8", errors="ignore").read()
    print("=====", n, len(s), "nodes:", len(re.findall(r"<node", s)))
    for m in re.finditer(r"<node[^>]*>", s):
        t = m.group(0)
        attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', t))
        blob = " ".join((attrs.get("text", ""), attrs.get("content-desc", ""),
                         attrs.get("resource-id", ""), attrs.get("class", "")))
        if PAT.search(blob):
            print("   cls=%-38s bounds=%-24s text=%-20r desc=%-20r rid=%r" % (
                attrs.get("class", ""), attrs.get("bounds", ""),
                attrs.get("text", "")[:20], attrs.get("content-desc", "")[:20],
                attrs.get("resource-id", "")[:50]))
