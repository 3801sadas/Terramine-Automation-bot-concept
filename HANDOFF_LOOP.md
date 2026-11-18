# HANDOFF — Autonomous Gold Rush loop (no LLM in the loop)

**Audience:** the other agent fork working on the TerraMine project.
**Author:** main fork, session 2026-11-11.
**Goal:** make the game loop run unattended on the physical device, with **zero LLM calls** and **zero subscriptions**.
**Non-negotiable:** the LLM is *not* part of the runtime. All decisions must come from the Android UI tree, the solver, or OpenCV. See §9 for why.

---

## 1. Scope

Play TerraMine's **Gold Rush** minigame (`com.terramine.app`, v1.1.45) on device `R5CT63BQTTH` in a loop:

capture → perceive → solve → validate → tap → handle result → handle ad → repeat.

Only enter mines with **Game Level < 100**. Only the Gold Rush minigame.

---

## 2. Invariants — violating any of these loses the user reward or money

1. **1 tap = 1 move = 90° clockwise rotation.** There is no undo.
2. **Move budget is `48`.
   Never plan a solution that exceeds `46` total taps.** `solve_from_image.py` already enforces `max_total = 46`.
3. **Intentional mistakes are wanted, capped at +8 taps** (2 mistakes × [1 wrong + 3 fix]). Never exceed 8, never push the plan past 46. This is an explicit user request — do not "fix" it.
4. **On time-up: do nothing.** No taps, no re-entry, no recovery. Exit the loop and report. This is a hard user rule.
5. **On out-of-moves: tap `🚪 Quit`, then re-enter the mine.**
6. **Never rotate LEP or POT.** They are fixed border pieces: LEP is open toward the board, POT likewise. `perception_v2` forces this; keep it.
7. **Never tap outside these safe regions while an ad may be on screen:**
   `mid_right`, `top_right`, `top_left` (see §6). Never tap ad content, never tap the `Install` button.
8. **Do not close a rewarded ad before the reward is confirmed** ("Reward granted" text or end card), or the reward is forfeited.

---

## 3. Verified facts (use these, don't re-derive)

### Device & geometry
- Serial `R5CT63BQTTH`, screen `1080×2340`, density 480.
- `calibration.json` → board rect `(36,503)–(1043,1510)`, 6×6, `cell_w = cell_h = 167.83`.
- Cell centres: `x = 119.9 + 167.83*c`, `y = 586.9 + 167.83*r`.
- The board rect is **stable** across boards, including when a level-up banner is showing. Verify with the yellow-border scan in §10 before trusting it.

### UI tree strings (verified live — match on these, not on pixels)
The app exposes real accessibility nodes with `content-desc` and exact `bounds`:

| Screen element | `content-desc` | Verified bounds |
|---|---|---|
| Free play again | `🔄 Play Again` | `[220,1851][587,1962]` |
| Rewarded play again | `📺 Watch Ad → Play Again` | `[99,1851][707,1962]` |
| Rewarded level replay | `📺 Watch Ad → Play Level 57` | `[242,1243][839,1332]` |
| Exit | `🚪 Exit` | `[743,1851][981,1962]` |
| Ad-not-ready dialog | `OK` (`android:id/button1`) | `[777,1218][969,1362]` |

**Match by stripping non-ASCII and doing a substring test** (`"Watch Ad"`, `"Play Again"`, `"Exit"`), because emoji encoding varies (`&#128250;`).
**Always resolve tap coordinates from `bounds` at runtime.** Never hardcode a button centre: the result panel has at least two layouts (with reward tiles / without), and the button y-position differs.

### Other screen signatures
- Board: present `content-desc` like `← Back`, text `Level 57 · Master`, `48 left`, `0/1000 XP`.
- Result: text `Pot of Gold Found!`, `Score: NNN · Taps: NN`.
- Level up: text `⬆️ LEVEL UP! Now Level NN`.
- Ad loading: text `Loading ad...` (replaces the button, keeps `🚪 Exit`).
- Ad WebView: `dump_ui` returns essentially **one node** — `android.webkit.WebView` with `bounds="[0,81][1080,2196]"` and a `navigationBarBackground` sibling. **No close button is exposed.** This is the only state that requires vision.

### Ads observed
Three networks in the manifest: AdMob, Meta Audience Network, Unity Ads. Confirmed real cases:
- AdMob playable (Pikmin Bloom): full-screen WebView, alphabet-puzzle, "Reward granted" + **X at (1007,152)** top-right, ~40–60 s.
- Two earlier rewarded videos with close at ~**(975,584)** and **(993,581)** (mid-right).
- **"Ad Not Ready"** appears if you tap `Watch Ad` too early; dismiss `OK`, wait 20–30 s, retry once. Observed twice.

---

## 4. What already exists — do NOT rebuild

| File | Purpose |
|---|---|
| `src/solve_simple.py` | Branch-and-bound **simple-path** solver + plan validator (apply taps → BFS LEP→POT). Source of truth for feasibility. |
| `src/perception_v2.py` | Exemplar NCC + LEP/POT border heuristics + grass detection. Loads labels from `Memory/derived/labels/ground_truth.json`. |
| `src/solve_from_image.py` | Entry point: perceive → solve → validate → emit `TAPS_JSON` + `TOTAL_TAPS`. Flags: `--exclude`, `--no-mistakes`, `--mistakes N`. |
| `src/label_board.py` | Overlay + correction template + `--save` into the label store. |
| `src/ad_detector.py` | OpenCV X detection (Hough diagonal crossing + synthetic X templates) over safe regions; loads priors from `ad_close_points.json`. |
| `src/ad_close.py` | CLI: `scan`, `sample`, `add-point`, `points`. |
| `Memory/derived/ad_close_points.json` | Known close points: `(975,584)`, `(993,581)`, `(1007,152)`. Canonical — merge, don't replace. |
| `Memory/derived/labels/ground_truth.json` | 4 labelled boards (`run_01`, `fresh_01`, `fresh_tshape_01`, `loop_01`). |

**CLI contract you can depend on:**

```
python src/solve_from_image.py <img> [--exclude] [--mistakes N | --no-mistakes]
> LEP=(r, c) POT=(r, c)
> COST 24 (validated) +8 mistakes = 32 total
> TAPS_JSON=[{"r":5,"c":1,"x":288,"y":1426}, ...]
> TOTAL_TAPS=32
```
Exit code `1` + `NO VALID SOLUTION (perception may be wrong)` means **do not tap anything**.

---

## 5. What to build

### 5.1 `src/screen_state.py`
`classify(ui_xml_path) -> (state, elements)` where `state ∈ {BOARD, RESULT_FREE, RESULT_AD, LEVEL_UP, AD_LOADING, AD_WEBVIEW, AD_NOT_READY, DIALOG_UNKNOWN, MENU, UNKNOWN}`.

Rules, in priority order:
1. `android.webkit.WebView` covering >80 % of the screen → `AD_WEBVIEW`.
2. Node `android:id/button1` with text `OK` and text containing `Ad Not Ready` → `AD_NOT_READY`.
3. Text contains `Loading ad` → `AD_LOADING`.
4. `content-desc` matches `Watch Ad` + `Play Level` → `LEVEL_UP`.
5. Text contains `LEVEL UP!` and `content-desc` matches `Watch Ad` → `LEVEL_UP`.
6. Text contains `Pot of Gold Found!`:
   - `content-desc` matches `Watch Ad` → `RESULT_AD`
   - else `content-desc` matches `Play Again` → `RESULT_FREE`
7. Text contains `Level` + `left` + `Tap road tiles to rotate` or a grid of 36 clickable cells `[45,222]…` → `BOARD`.
8. Anything else → `UNKNOWN`.

Return elements as `{name: (cx, cy)}` computed from `bounds` **at classification time**.

### 5.2 `src/ad_close_loop.py`
```
def close_ad(shot_fn, max_attempts=12, poll_s=8) -> "closed" | "timeout" | "unsafe"
```
- Poll: screenshot → `find_close_candidates(img)`.
- **Gate on context first**: only act if the screen is `AD_WEBVIEW` (via `dump_ui`) or the screenshot is not a known game screen. This gate exists because the detector produced a false positive at `(962,561)` on a *result* screen — it still reports `score 1.0` there. **The score alone is not sufficient.**
- Accept a candidate if `score ≥ 0.70` **and** it lies in `mid_right`/`top_right`/`top_left`, **or** it is within 40 px of a known point.
- Tap, wait 3 s, re-classify:
  - `AD_WEBVIEW` still → continue loop.
  - `BOARD` → `closed` (success; step 5.5).
  - `MENU`/store page/unknown → `unsafe`, stop, screenshot, report. Never keep tapping.
- No candidate found → keep polling. Ads have been observed to take 25 s+ to become ready and 40–60 s to expose the X.
- Hard stop after `max_attempts` → `timeout`, screenshot, report.
- **Training hook:** on every successful tap, `save_sample(img, x, y, note=f"{state}")` into `Memory/derived/ad_close/samples/`.

### 5.3 `src/run_loop.py`
State machine, one iteration per screen:

```
BOARD          → solve_from_image(img)
                 exit 1          → save shot to queue/, goto UNKNOWN_HOLD
                 TOTAL_TAPS > 46 → refuse, queue, halt
                 else            → batch_tap(delay_ms=130), wait 4–5 s
RESULT_FREE    → tap "Play Again"  → BOARD
RESULT_AD      → tap "Watch Ad"    → AD_LOADING, then close_ad()
LEVEL_UP       → tap "Watch Ad"    → AD_LOADING, then close_ad()
AD_LOADING     → wait 5 s, re-classify; if AD_NOT_READY → dismiss, wait 25 s, retry once
AD_NOT_READY   → tap OK, sleep 25 s, retry "Watch Ad" once only
AD_WEBVIEW     → close_ad()
OUT_OF_MOVES   → tap "Quit" → menu → re-enter mine
TIMEOUT        → log, halt, do nothing
UNKNOWN        → log, screenshot, halt (do not guess)
```

Guardrails:
- Global cap of e.g. 200 iterations, then halt and report.
- Sleep 4–5 s after a tap batch (the win panel takes ~3–4 s).
- Detect `48 left` → `0 left` transitions to confirm moves actually registered; if the move counter did not decrement after a tap batch, do **not** re-tap blindly — screenshot and halt.
- If the same `TAPS_JSON` is emitted for two boards in a row with identical screenshots, halt (stuck detector).

### 5.4 Timing / stale-frame handling
Screenshots after a tap can be blank or truncated. Read the PNG; if `img.size != (1080, 2340)` or mean brightness < 5, re-shoot once. Never classify a black frame.

### 5.5 Post-close verification
After `close_ad()` returns `closed`, wait 2–3 s and re-classify. If the state is `RESULT_FREE`/`RESULT_AD` (the reward panel re-appears behind the ad), tap the button again — some flows need two taps. Cap at 3.

---

## 6. Ad safe regions (1080×2340)

```python
mid_right  = (860, 480, 1065, 700)   # confirmed (975,584) (993,581)
top_right  = (920,  20, 1075, 220)   # confirmed (1007,152)
top_left   = (  5,  20,  180, 260)
top_center = (420,  20,  660, 200)   # low prior, template only
```

---

## 7. Failure queue — how the project improves without an LLM

When `solve_from_image.py` returns `NO VALID SOLUTION`, or the state is `UNKNOWN`:
1. Copy the screenshot to `Memory/derived/queue/<timestamp>_<reason>.png`.
2. Append a line to `Memory/derived/queue/index.jsonl`: `{image, reason, lep, pot, predicted_grid}`.
3. Halt (default) or continue to the next board (config).

The user annotates the queue in Excel later (rows 1–6, cols A–F; `1A` = top-left), and the entries get merged into `ground_truth.json` — which is how the exemplar library grows. **Do not invent a labelling model for this.**

---

## 8. Acceptance tests

1. **Replay test:** run the loop on `Memory/derived/device/loop_02.png` and `loop_03.png`; the emitted plans must match the recorded ones (`loop_02` = 11 base / 19 total, `loop_03` = 25 base / 33 total).
2. **No-solution test:** a board that fails perception must produce **zero taps**.
3. **Ad test:** from `RESULT_AD`, `AD_NOT_READY` must be handled exactly once, then either a close or a safe stop — never an unbounded tap loop.
4. **10-board run:** 10 consecutive boards unattended; every board either wins or is queued; **zero** taps outside the board rect or ad safe regions.
5. **Timer test:** simulate the clock hitting zero; the loop must perform **no** action.

---

## 9. Non-goals (explicitly out of scope)

- **No LLM at runtime.** Measured on the target laptop (i5-1235U, Iris Xe, 16 GB): `qwen2.5vl:7b` on a 1080×2340 screenshot = **539 s per decision**. Unusable. Text-only is ~15 s warm — still slower and less accurate than a `content-desc` lookup.
- No cloud APIs, no subscriptions, no model downloads in the loop path.
- No changes to the solver's correctness guarantees.
- Don't replace `dump_ui`-based classification with vision.
- Don't add a "smart" retry that taps on a timer without verification.

---

## 10. Pitfalls learned the hard way

1. **Screenshot previews are rescaled.** Eyeballing coordinates from a rendered image is how we tapped *(540,1185)* and *(540,1115)* on a button that actually lives at `[242,1243][839,1332]`. **Only `dump_ui` bounds are authoritative.**
2. **The X detector false-positives at ~`(962,561)`** on normal game screens (score 1.0 via Hough). Context gating is mandatory, not optional.
3. **Result panels vary.** Button y-position and presence of the rewards grid differ per outcome. Re-read bounds every time.
4. **`Ad Not Ready` is common** if you tap too quickly after the result panel appears.
5. **Taps can silently fail** if the game window lost focus or the phone slept. User has screen-timeout raised; still verify the move counter decremented.
6. **Two-tap success flows exist** (Play Again → rewards panel → Play Again).
7. **Don't delete old screenshots.** Exclusion from the exemplar pool is a profile choice, not a deletion.
8. Never exceed the 46-tap guard, even if the solver finds a cheaper route later.

---

## 11. Logging contract

One JSONL record per board in `Memory/derived/run_log.jsonl`:

```json
{"ts":"...","image":"...","lep":[1,0],"pot":[0,5],"base_cost":11,"mistakes":2,
 "total_taps":19,"plan":[...],"result":"win|queued|aborted|timeout","score":839,"taps_reported":19,
 "ad":{"triggered":true,"close_point":[1007,152],"outcome":"closed","attempts":2}}
```

Also keep the annotated perception overlay per board (`label_board.py`) — it's the fastest way to debug a bad read.

---

## 12. Handover checklist

- [ ] Merge `ad_close_points.json` (3 points) — this fork's file is canonical.
- [ ] Copy the ad samples in `Memory/derived/ad_close/samples/` into the shared pool, including `samples.jsonl`.
- [ ] Add the 3 confirmed ad cases to §3 if you find variants (network, layout, X position).
- [ ] Keep `ground_truth.json` append-only; re-labelling a board replaces by image path.
- [ ] Report back with: boards played, wins, queue size, ad outcomes, and any new content-desc strings discovered.
