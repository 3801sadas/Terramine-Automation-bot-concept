"""Text-only latency test: no image, just a UI-tree excerpt."""
import json, time, urllib.request, sys

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:7b"

prompt = (
    "Below is an Android UI tree excerpt. Output ONE line of JSON only.\n"
    '{"screen":"result|board|ad|dialog|menu|unknown",'
    '"action":"tap_watch_ad|tap_play_again|tap_close|wait"}\n'
    'TREE: content-desc="Watch Ad -> Play Again" bounds="[99,1851][707,1962]"; '
    'text="Pot of Gold Found!"; text="Score: 760 - Taps: 33"; '
    'content-desc="Exit" bounds="[743,1851][981,1962]"'
)

payload = {
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "options": {"temperature": 0, "num_predict": 60, "num_ctx": 2048},
}

t0 = time.time()
req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
d = json.loads(urllib.request.urlopen(req, timeout=600).read())
dt = time.time() - t0
pe = d.get("prompt_eval_duration", 1) / 1e9
ed = d.get("eval_duration", 1) / 1e9
print(f"wall={dt:.1f}s load={d.get('load_duration',0)/1e9:.1f}s "
      f"prompt={d.get('prompt_eval_count',0)}tok/{pe:.1f}s "
      f"gen={d.get('eval_count',0)}tok @ {d.get('eval_count',0)/ed:.1f}tok/s")
print("raw:", repr(d.get("response", "")[:200]))
