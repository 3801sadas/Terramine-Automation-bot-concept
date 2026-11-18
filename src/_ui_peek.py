import re, sys
p = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Usernom\Documents\Terramine\Memory\derived\debug\ui_levelup.xml'
s = open(p, encoding='utf-8', errors='ignore').read()
print('len', len(s))
for m in re.finditer(r'<node[^>]*>', s):
    t = m.group(0)
    if 'clickable="true"' in t or 'Watch' in t or 'Level' in t or 'Play' in t:
        print(t[:500])
