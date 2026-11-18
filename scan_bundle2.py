import re, sys

path = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure\assets\index.android.bundle"

with open(path, 'rb') as f:
    data = f.read()

text = data.decode('utf-8', errors='ignore')

# Look for API endpoints and specific function names
patterns = [
    r'submitGameResult',
    r'goldrush',
    r'GoldRush',
    r'game.*result',
    r'ad.*reward',
    r'claim.*reward',
    r'withdraw',
    r'purchase.*validate',
    r'redeem',
    r'balance.*update',
    r'/api/',
    r'functions\.run',
]

for p in patterns:
    matches = re.findall(p, text, re.I)
    if matches:
        uniq = list(set([m[:60] for m in matches]))
        print(f'=== {p} ({len(matches)} total) ===')
        for m in uniq[:40]:
            print(m)
        print()
