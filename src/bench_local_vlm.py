"""Time a local VLM on a real TerraMine screenshot via Ollama's HTTP API."""
import base64, json, sys, time, urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5vl:7b"
IMG = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\Usernom\Documents\Terramine\Memory\derived\device\ad_live_03.png"
PROMPT = (
    "You are controlling an Android game. Reply with ONE line of JSON only:\n"
    '{"screen":"result|board|ad|dialog|menu|unknown","action":"tap_watch_ad|tap_play_again|tap_exit|close_ad|wait","x":<int or 0>,"y":<int or 0>}\n'
    "Coordinates are for a 1080x2340 screenshot."
)

with open(IMG, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

payload = {
    "model": MODEL,
    "prompt": PROMPT,
    "images": [b64],
    "stream": False,
    "options": {"temperature": 0, "num_predict": 80, "num_ctx": 4096},
}

req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as r:
    data = json.loads(r.read())
dt = time.time() - t0
print(f"model={MODEL}")
print(f"wall={dt:.1f}s  load={data.get('load_duration',0)/1e9:.1f}s  "
      f"eval={data.get('eval_count',0)}tok @ {data.get('eval_count',0)/(data.get('eval_duration',1)/1e9):.1f}tok/s")
print("raw:", repr(data.get("response", "")[:400]))
