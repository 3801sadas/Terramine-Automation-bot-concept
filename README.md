# (Working but incomplete) Terramine automated Gold Mine minigame solver
**This readme was made by AI as I am busy and actually have a life**

An unattended bot that plays the **Gold Rush** minigame in TerraMine Gold Mine maze minigame
(`com.terramine.app`) on a real Android phone. It captures the screen over ADB,
reads the board with local computer vision, solves the tile-rotation puzzle,
validates the plan offline, taps it, and repeats — including through rewarded
ads.

**No LLM at runtime.** The whole loop is `adb` + `numpy` + `Pillow` + local
Python. The game *rules* were recovered once from the decompiled Unity/Hermes
bundle; after that the loop runs on pixels and a small state machine.

```
capture → perceive → solve → validate → tap → verify → repair → result → ad → repeat
```

---

## How the game works

Each board is an `N × N` grid of road tiles. A **Leprechaun (LEP)** sits on the
left edge, a **Pot of Gold (POT)** on the right. Tapping a tile rotates it
**90° clockwise**, costing one move. The goal is a continuous road from LEP to
POT before the timer or the move budget runs out.

| rule | value |
|---|---|
| tap effect | +90° clockwise |
| move budget | 48 (the bot never plans more than **46**) |
| grid sizes | 4×4, 5×5, 6×6 (board size grows with player level) |
| LEP / POT | deterministic border pieces — **never tapped** |
| board rect | `(36, 503) → (1043, 1510)`, cell = `1007 / N` |

---

## Features

- **Pixel perception** — seam-detected grid geometry, per-tile arm
  classification, template matching for LEP/POT. Falls back through 4/5/6
  grid sizes when the seam detector is unsure.
- **Validated plans** — the solver simulates every tap and BFS-checks that the
  resulting grid really connects LEP → POT *before* a single tap is sent.
- **Self-repair** — after the plan, the board is re-read; if a rotation was
  dropped, only the missing residual taps (≤ 8, max 2 rounds) are applied.
- **Intentional mistakes** — optional wrong-then-fix rotations, capped at
  +8 taps, and never allowed to consume the whole move budget.
- **Ad handling** — recognises AdMob creatives, Play-Store sheets and
  "Ad Not Ready"; closes them with a visually confirmed close glyph or an
  early `BACK` instead of blind taps. Reward badges are detected from the
  screenshot (`Reward in N s` → `Reward granted`).
- **Dead-board safety** — red-clock boards, Time's Up panels and the
  "Out of moves!" overlay are never tapped.
- **Crash resilience** — screenshot retries, ADB reconnection, display wake,
  watchdog, and a supervisor that restarts the loop after a failure.

---

## Requirements

- Windows (paths are Windows-style) with **Python 3.10+**
  (developed on 3.14)
- **ADB** with one authorised device — set the path in `src/device.py`
- Python packages:

```bash
pip install pillow numpy
```

- An Android device at **1080×2340** portrait (screen size is asserted)
- TerraMine installed, logged in, with Gold Rush unlocked

Device serial, package name and screen size live at the top of
`src/device.py` and in `calibration.json`.

---

## Usage

Check the device is visible first:

```bash
adb devices
```

Solve a single screenshot:

```bash
python src/solve_from_image.py shot.png --exclude
```

Options: `--no-mistakes`, `--mistakes N`.


**Explanation** Mistakes here can be configured, because if the bot intentionally makes mistakes you actually get more TB in the long term
Before running the below Python Script please navigate into a Gold Mine maze minigame that is under Level 100 for it to work.

Run the loop for a fixed number of boards:

```bash
python src/run_loop.py --max 20 --wait 2 --log run.log
```

| flag | meaning |
|---|---|
| `--max N` | stop after `N` boards |
| `--wait M` | when parked on a dead board, poll up to `M` minutes for a fresh one (zero taps in the meantime) |
| `--log PATH` | mirror the console output to a file |
| `--dry-run` | classify and solve only — never taps |

Run the loop forever under the supervisor:

```bash
python src/endless.py --max 50
```

Run the regression suite (no device needed):

```bash
python src/test_runtime.py
```

---

## How a board is played

1. **Capture** a frame and classify the screen from the UI tree
   (`BOARD`, `RESULT_FREE`, `RESULT_AD`, `LEVEL_UP`, `TIME_UP`, `OUT_OF_MOVES`,
   `AD_WEBVIEW`, `AD_STORE`, `AD_NOT_READY`).
2. **Refuse dead boards** — red timer, Time's Up or out-of-moves → zero taps.
3. **Perceive** the tiles and solve for the cheapest valid tap sequence.
4. **Re-capture and re-solve** if the plan looks degenerate or would spend the
   entire move budget.
5. **Tap**, then verify: result panel, or a residual repair, or halt if the
   move counter did not even decrement.
6. **Log** the board, plan, repairs and outcome to JSONL.

---

## Project layout

```
src/
  run_loop.py        main state machine (the bot)
  endless.py         supervisor: restarts the loop forever
  device.py          adb wrapper: screenshots, taps, UI dumps, recovery
  screen_state.py    screen classification from the UI tree
  perception_v2.py   grid geometry + tile arm reading
  tilegrid.py        playfield frame and cell centres
  solve_simple.py    simple-path solver + plan validation
  solve_from_image.py  CLI: image -> validated tap list
  ad_close_loop.py   ad detection and closing
  ad_detector.py     close-glyph template matching
  ad_reward.py       "Reward in N s" badge detector
  test_runtime.py    offline regression suite
Memory/
  User learning videos and pictures/   source material (untouched)
  derived/
    PROBLEMS.md      numbered incident log with evidence and fixes
    boards/          archived board frames
    queue/           archived failures for labelling
    endless_*.log    run logs
calibration.json     device + playfield calibration
STATE.md             narrative run history
version.log          append-only change log
```

---

## Rules the bot follows

These are hard constraints, enforced in code and in tests:

- **Time's Up → do nothing at all.** No taps, no re-entry.
- **Never tap ad content or an `Install` button** — only a visually confirmed
  close glyph (score ≥ 0.70) or a UI-tree `Close`.
- **Never rotate LEP or POT.**
- **Never plan more than 46 of the 48 moves.**
- **Never credit a dead board as a win** — the result panel is confirmed
  separately from the Time's Up panel.
- **Out of moves → `Quit`, then re-enter.**

---

## Results

Tracked in `STATE.md` and `Memory/derived/PROBLEMS.md`:

- **100/100** consecutive 6×6 boards solved, and **92/92** in a later batch.
- Recent supervised runs: **14/14** boards won with zero dead boards after the
  move-budget fix (P013).

Every failure that cost a board was logged with its frame, timeline and root
cause (P001–P013) before being fixed. That log is the most useful part of this
repo if you want to see how the perception and ad handling actually break.

I was joking. It still sucks and fails a lot but it is mostly automatic but may require some supervision
Perception takes a long time (analysing the phone screen)
Actual solving and taps are REALLY FUCKING fast

---

## Notes & limitations

- Built for one specific device resolution and one app build; the ad SDK's
  creatives change over time, and a long ad chain can still outlast a board's
  60 s clock.
- `adb` and the device serial are hard-coded — edit `src/device.py` (and
  `src/endless.py`) for your setup.
- The decompiled bundles (`goldrush_bundle.txt`, `tb_bundle.txt`) are included
  for rule provenance only; the runtime never reads them.
- For personal/educational use. Automating a game ~~may~~ will violate its terms of
  service — use at your own risk.
- The devs have confirmed that more ad partners will be rolling out in the game
- ~~If you want to bypass the ads between the games "watch ad - Play Again" then roll back to version 1.39 and use InstallWithOptions to set the installation source to com.android.vending~~ That also violates the TOS I think so maybe don't do that
