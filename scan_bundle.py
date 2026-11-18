import re, json, sys

path = sys.argv[1] if len(sys.argv)>1 else r"C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure\assets\index.android.bundle"

with open(path, 'rb') as f:
    data = f.read()

# Try to decode as UTF-8 with errors ignored
text = data.decode('utf-8', errors='ignore')

# Look for patterns
patterns = [
    r'submitGameResult\w*',
    r'goldRush\w*',
    r'gameReward\w*',
    r'reward.*[Tt]b',
    r'[Tt]b.*reward',
    r'add.*balance',
    r'claimReward\w*',
    r'watchAd.*reward',
    r'adReward\w*',
    r'purchase.*verify',
    r'api.*reward',
    r'cheat\w*',
    r'exploit\w*',
]

for p in patterns:
    matches = re.findall(p, text, re.I)
    if matches:
        # Get unique
        uniq = list(set(matches))
        print(f'=== {p} ===')
        for m in uniq[:30]:
            print(m)
        print()
