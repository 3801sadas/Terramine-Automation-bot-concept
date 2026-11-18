# TerraMine Gold Rush Automation — Project State

_Last updated: 2026-11-10_

## Goal
Automate the **GoldRushGame** in TerraMine (Android) so it is completed repeatedly; rewards are credited automatically.
- Physical phone, controlled via AgentDroid (MCP).
- Hybrid approach: screenshots/vision for the live board + decompiled APK/Hermes bundle for game rules.
- **Ignore all other minigames for now** (Miner Maze, Laser Blast, Memory Match, etc.).

## Paths
- Project root: `C:\Users\Usernom\Documents\Terramine`
- Raw training media: `C:\Users\Usernom\Documents\Terramine\Memory\User learning videos and pictures` (empty so far; user will add screenshots/video)
- Derived artifacts: `C:\Users\Usernom\Documents\Terramine\Memory\derived` (to be created when needed)
- Decompiled APK: `C:\Users\Usernom\Downloads\TerraMine_+Real+World+Mining_1.1.45_APKPure`
- AgentDroid install: `C:\Users\Usernom\AgentDroid`
- JS bundle: `<APK>\assets\index.android.bundle` (Hermes bytecode, ~6 MB)

## Findings so far
- App: `com.terramine.app`, v1.1.45, Expo/React Native (new arch), Hermes bundle.
- Gold Rush is a **rotate-tiles-to-connect-path puzzle**: leprechaun -> pot of gold.
- Tile types: grass, straight, curve, T-junction, cross, dead-end.
- Relevant symbols: `getTileConnections`, `rotateConnections`, `stitchTile`, `PathPieces`, `isSolutionPath`,
  `GoldRushGridSize`, `GoldRushMovesLimit`, `GoldRushPerfectThreshold`.
- UI/strings: "The leprechaun couldn't find the way...", "Saving results...", "GoldRushGame Level:".
- Rewarded-ad move extensions exist ("moves added! Keep playing!").
- Tile art: `<APK>\res\drawable-mdpi\assets_images_goldmine_tile*.png`; leprechaun idle/walk/celebrate; pot of gold; background.
- Prior leftover analysis: `C:\Users\Usernom\AgentDroid\board_crop.py` cropped a board at `(28,255)-(691,935)` from `rush_now.png` (source PNG missing). Implies near-square board on a 720x1440 screen, likely 5x5–7x7.
- Device status: none connected at last check (`agentdroid.list_devices` returned empty).

## Phase progress
- Phase 0 (device bring-up): DONE. Device `R5CT63BQTTH` connected; screenshot ok; screen 1080x2340, density 480; app v1.1.45.
- Phase 1 (board calibration): DONE. Board rect `(36,503)-(1043,1510)`; 6x6; cell ~167.83 px; centers saved to `calibration.json`.
- Phase 2 (perception): IN PROGRESS. `src/perception.py` (RGB template NCC vs APK tiles) gives ~0.83-0.91 but poor discrimination. `src/fast_solve.py` now uses bright-road mask + edge+inward sampling; produces varied tile types but **not yet validated as correct**. Lep/pot heuristics added (unverified).
- Phase 3 (solver): IN PROGRESS. Dijkstra-with-rotations in `fast_solve.py`; solver must reject impossible paths (tc=99 / grass pass-through). Rotation semantics still assumptions.
- Phase 4 (live round): ATTEMPTED (autonomous). Brute-force rotation sweeps completed 1 level and reached Play Again; got stuck on ad (ad handling deferred). Timed execution failed on later attempt due to perception errors. Screenshots: `run_01..04.png`, `auto_01..06.png`.
- Phase 5/6: not started. Ad handling deferred.

### UPDATED 2026-11-10: pipeline now WORKING end-to-end
- Solver bug fixed: `src/solve_simple.py` enforces simple path (no revisits) + BFS validation before returning a plan. Reproduces known-good plans for run_01 (11 taps), fresh_01 (12), fresh_02 (10).
- Perception fix: LEP/POT are deterministic border pieces (LEP col0 -> E, POT col5 -> W). LEP found via very-dark sprite mass (0.14 vs <0.01 elsewhere) instead of green fraction.
- LIVE WINS: fresh_02 (LEP(1,0)->POT(3,5), 10 taps, Score 807), fresh_05 (LEP(3,0)->POT(3,5), 4 taps, Score 886), fresh_06 (LEP(1,0)->POT(5,5), 25 taps, Score 816).
- Pipeline latency: capture -> perceive -> solve+validate -> taps ~3-5 s total.
- Screen-off after >~60s idle caused board loss; set Screen timeout to 10 min or Developer options -> Stay awake while charging. Eye Comfort off still recommended.
- Reward flow: success panel -> tap reveals bonus breakdown -> "Play Again" (or "Watch Ad -> Play Level" -> Play Again). Free Play Again may appear; ad handling still deferred.

## Open questions
1. Does any completion count, or does "perfect"/fewer moves change rewards?
2. Auto-advance levels indefinitely, or replay same level?
3. Avoid ads entirely, or allow rewarded ad for extra moves?
4. Exact rotation gesture: tap = 90° CW? any CCW? (confirm from video)
5. Success flow: auto-next level vs return to menu vs ad interstitial.

## Next step
- Clean up / verify `src/solve_simple.py` and run on current boards; confirm `VALIDATED: True` before tapping.
- Continue loop: capture → perceive → validate → tap; stop/report on ad or on timeout (do nothing).
- Quickly re-label successful boards and add to `ground_truth.json` via `label_board.py --save`.

## Working protocol (credit-saving)
- Work in **small, verifiable chunks**; one focused step per turn.
- Persist findings in this file after each chunk.
- Avoid re-reading the 6 MB bundle; use targeted extraction and keep results here.
- Keep outputs short; no giant dumps.

### UPDATED 2026-11-11 (evening): no-LLM runtime built (per HANDOFF_LOOP.md)
- New modules: `src/device.py` (adb wrapper: screenshot/tap/dump_ui/parse), `src/screen_state.py` (UI-tree state machine), `src/ad_close_loop.py` (ad poll/tap/verify), `src/run_loop.py` (unattended loop), `src/test_runtime.py` (offline tests, all pass).
- States: BOARD / RESULT_FREE / RESULT_AD / LEVEL_UP / AD_LOADING / AD_WEBVIEW / AD_NOT_READY / OUT_OF_MOVES / TIME_UP / MENU / UNKNOWN. Button coords always resolved from `bounds`.
- Live run (3-board test) results: 2 wins via loop (24 and 26 taps). Ad flow closed AdMob playable at (1008,153) from AD_WEBVIEW.
- **Critical discovery: the board clock keeps running while an ad plays.** A long ad + futile close-taps ate ~3 min and produced "Time's Up! (0s)". Time-up is now classified before BOARD and the loop performs **zero** actions on it.
- Ad-tap policy hardened after live failure: visual X first, remembered points only after poll #5, max 2 taps per point, max 8 taps/ad, no taps while the ad frame is byte-identical (countdown).
- Result-panel stall guard: if an actionable state survives 4 consecutive taps unchanged, halt + queue (previously it tapped "Play Again" 11x pointlessly).
- Known ad layouts confirmed: AdMob playable -> X top-right (1007,152); rewarded video -> X mid-right ~(963,601)/(975,584)/(993,581).
- Queued perception failure: `Memory/derived/queue/*` for the Level-59 board that hit time-up (annotation pending).
- Session wins (manual+loop, Level 57-59): scores 625, 839, 760, 775.

### UPDATED 2026-11-12: loop optimized + supervised runs
- New: `device.snapshot_pair()` (screenshot+UI dump in parallel, ~2.6 s), `device.tap_batch()` (all taps in one adb shell call).
- `dump_ui` now has a **14 s hard budget** (uiautomator hangs during win animations and was burning 120 s+ of board clock), deletes the remote file first, and retries quickly.
- Visual helpers (no OCR): `looks_like_game()` (gold board frame: >=2 full-width rows + >=2 vertical borders) and `looks_like_result()` (yellow button band in y 1780-2020, width>250 px). Verified: boards -> game True/result False; results+level-up -> both True; ads -> both False.
- `run_loop` uses a screenshot-only win check after taps, so the hot path no longer depends on uiautomator.
- Ad loop: screenshot-only fast path (board visible -> closed), 3 s polls, skips the dump on byte-identical frames, max 2 taps/point, max 8 taps/ad, remembered points only after poll 5.
- Tests: 10/10 in `src/test_runtime.py`.
- Live results this session: 4 boards won unattended (24, 26, 41, 12 taps), ads closed; remaining failures were all clock loss from the dump hang (now fixed).

### UPDATED 2026-11-12 (evening 2): fast, dump-free board path + rewarded-ad policy
- `run_loop` now takes a **screenshot first** and classifies visually; a plain BOARD iteration never calls uiautomator (1.3-1.8 s per iteration instead of 30-44 s).
- `looks_like_levelup()`: detects the solid `LEVEL UP!` banner via a large yellow connected component (~693x198 px, area >= 90k). `looks_like_result()` now needs >=30 contiguous wide-yellow rows in y 1840-1980 (time-up/Try Again band also matches, which is fine because the UI dump resolves it).
- Panel detection order: levelup -> result -> board; a stale UI tree over a panel triggers one re-dump, then halts instead of blind-tapping.
- `tap_batch()` now sleeps 120 ms between taps (the game drops back-to-back input events = the "missed last tile" bug) and the loop runs a **self-repair pass** (re-solve from the new screenshot, <=8 residual taps, max 2 tries) when the board is still up.
- **Rewarded ads**: `close_ad(reward_wait=75)` never taps an X while the creative is playing (`Ad N of 3 - Reward in M`), so the reward is always granted; it only hunts for an X after 75 s. Play-Store end cards are a new `AD_STORE` state (root package + `Close` bounds) - it taps Close, never the `Install` button. Ads that never close now halt the run instead of looping.
- `device.ensure_awake()` / `recover_display()`: keeps the screen on (`svc power stayon`, infinite timeout), wakes/swipes a lock screen, and bounces the app if the frame is too dark (the phone locked itself mid-session and a stuck dim overlay was captured).
- New guard: max 3 Watch-Ad triggers per panel with no board, then halt (no ad loop).
- Tests: all pass in `src/test_runtime.py` (9 groups, incl. new AD_STORE + rewarded-wait cases).
- **Live results: 8/8 boards won unattended in two runs** (20 taps x2, 26, 20, 31, 25, 24, 25, 25, 12). Rewarded 3-video sequences (incl. Play-Store end cards) closed correctly; level-up ad handled; boards now take ~10 s each.

### UPDATED 2026-11-15: endless mode + hang protection
- **Run 1: 100/100 boards won**, 0 unknown/halts/stalls/time-outs; 20 level-ups, 11 Play-Store end cards, 1 self-repair. Stopped only by a stale `iterations < 200` cap (100 boards x 2 iterations) -> cap now `max(400, max_boards * 8)`.
- **Run 2: 53/53** before a manual restart.
- `run_loop.py --log FILE`: logs are written and flushed from Python (PowerShell `*>` buffered the file for minutes and made healthy runs look stuck).
- **Watchdog thread**: if a step blocks >240 s (adb/`uiautomator` wedges are real and leave `adb.exe` children hung), it kills `adb.exe` and exits rc=3 so the supervisor restarts.
- **Ads close as soon as the creative ends**: `close_ad` also leaves the reward wait when the frame has been frozen for 3 polls (>=15 s), instead of always waiting the full 75 s. Reward is still never dismissed mid-video.
- **`src/endless.py` supervisor**: runs `run_loop.py --max 500` forever, one timestamped log per run (`Memory/derived/endless_*.log`), clears stale adb clients and re-wakes the device between runs, backs off after repeated quick failures.



### 2026-11-15 late: run stopped on request
- Supervisor run `endless_20261115_191701_001.log`: **92/92 boards won**, 0 halts, 4 residual self-repairs, 10 level-ups, several Play-Store end cards closed with `Close`.
- Stopped cleanly on user request: supervisor + `run_loop` killed, no python/adb children left, phone idle on home screen.
- Fixed a logging gap: `run_loop` called `close_ad()` without `log=log`, so all `[ad] poll ...` diagnostics went only to stdout. Ad traces (poll states, freeze detection, close point) now land in the `--log` file too. Tests still pass.

### 2026-11-15 late-2: resumed + stopped on request
- Resumed on a fresh board at **Level 88**; run `endless_20261115_205456_001.log` won **31/31 boards**, 0 halts, 3 self-repairs (1, 4, 2 taps), 4 level-ups (Level 88 -> 92), no Play-Store end card this time.
- Stopped cleanly on request; game left on the free **Play Again** result panel, no python/adb children left.
- New diagnostics added: every perceived board is archived to `Memory/derived/boards/` (32 boards kept) and the first repair of a board saves `queue/<ts>_repair_before/after.png`; JSONL now records `repairs` and `repair_taps`.
- Remaining weakness: occasional single-tile misread costs 1-8 repair taps. It is still inside budget (plans 12-40 + repair <= 48) but a large plan (40+) plus a big repair could exhaust the 48 moves -> that path degrades to out-of-moves quit/re-entry, which is handled.

### 2026-11-15: NEW 4x4 board (Level 1 - Novice) - grid size changed
- The game served a **4x4** board ("Level 1 - Novice", 0/1000 XP). Recorded first as **P001/P002** in `Memory/derived/PROBLEMS.md` (nothing tapped after the clock hit 0s, per policy).
- Geometry measured from `Memory/derived/device/board_new_01.png`:
  - UI clickable cells (uiautomator): `x 45/297/549/801/1044`, `y 461/713/965/1217/1460` -> 252 px cells. **Taps use these centres** (171/423/675/922 x 587/839/1091/1339).
  - Drawn tile grid (seam + template search): origin **(41,516)**, cell **252** px, i.e. offset **(+5,+13)** from the gold frame rect `(36,503)-(1043,1510)`; the 4th row/col is clipped by the frame.
  - Perception from the exemplar classifier is unreliable here (it was trained on 6x6 crops). The APK tile art (`res/drawable-mdpi/assets_images_goldmine_tile*.png`, 1024x1024, opaque) matches almost exactly: NCC over 6 types x 4 rotations gave 0.93-0.94 for road tiles and 0.89-0.91 for grass.
  - Independent confirmation with a gold-road mask: N/E/S/W arm coverage per cell agreed with every NCC label.
- Base tile art (rotation 0): `straighth`=NS, `curve`=ES, `tjunction`=NEW, `cross`=NESW, `deadend`=S, `grass`=none. 1 tap = +1 quarter turn CW = `k+1`.
- **Board read (r,c from top-left):**
  ```
  r0: LEP(E)   NW        grass     grass
  r1: grass    EW        SW        POT(W)
  r2: grass    NW        ES        grass
  r3: grass    grass     grass     grass
  ```
- **Solution (validated, 10 taps, simple path LEP -> r0c1 -> r1c1 -> r2c1 -> r2c2 -> r1c2 -> POT):**
  `r0c1 x3`, `r1c1 x1`, `r2c1 x1`, `r2c2 x2`, `r1c2 x3`  (10 taps, <= 46)
- Board clock expired during manual analysis (P002), so the plan was **not** applied. `src/solve_simple.py` and `perception_v2.py` are still hard-wired to 6x6 (P001) - N must become a parameter before the runtime can play these.

### 2026-11-16: grid-size agnostic pipeline (fixes P001)
- **New module `src/tilegrid.py`**: `detect_geometry()` finds N×N grid from tile seams (luminance 20th percentile dips, robust against sprite shadows). `road_sides()` reads 4 edge openings from a gold-road mask with cell-size-scaled thresholds.
- **`perception_v2.py`**: now auto-detects grid size. 6x6 boards use the exemplar NCC classifier (preserves existing accuracy); 4×4, 5×5, etc. use `road_sides()`.
- **`solve_simple.py`**: infers grid size from grid keys, bounds-checks with `0 <= r,c < N`.
- **`solve_from_image.py`**: uses `res["geom"]` for tap centres.
- **Validated**:
  - 4×4 board `board_new_01.png` → 10 taps, path LEP→r0c1→r1c1→r2c1→r2c2→r1c2→POT ✓
  - 6×6 `fresh_01.png` → 12 taps ✓
  - 6×6 `fresh_02.png` → 10 taps ✓
- All `src/test_runtime.py` tests pass (9 groups).
- P001 marked FIXED in `PROBLEMS.md`.

### 2026-11-16 15:40: P005 fixed - 4x4 boards were being mis-read as 6x6
- Root cause: `tilegrid._fit_grid()` required the detected seams to span nearly the whole board.
  A 4x4 board only has 3 *internal* seam lines (span = 2 cells), so the fit was always rejected
  and `detect_geometry()` silently fell back to the 6x6 calibration.
- Fixes: internal-seam span rule; single-axis mirroring (`seams_x`/`seams_y`);
  `looks_like_real_board()` accepts mirrored seams and an LEP+POT sanity check;
  `solve_from_image.py` retries N in {4,5,6} on the fixed frame when geometry is `default`;
  `run_loop.py --wait <min>` polls with zero taps on TIME_UP/menu (rule-compliant).
- Verified: the wasted board `queue/20261116_152053_no_solution.png` now solves with cost 2;
  board_live_02 reads n=4; 4x4 + 6x6 regression all still solve; test_runtime all pass.
- Live run 004 started with `--wait 60` (idle on the Time's Up panel, no taps).

### 2026-11-16 15:44-16:37: supervised endless run 005 - 50/50 wins
- 4x4 boards (Level 1-6 Novice), no failures: every board solved and won.
- Plans: base cost 2-17, total (with intentional wrong-then-fix) 10-25, all <= 46.
- 4 boards needed a post-batch `residual repair: 1 tap`; all still won.
- Rewarded ads: 8 waits (75 s each), 12 Play-Store sheets closed via Close, zero Install taps.
- Fixed P006 after the run: result-panel detection is now colour-agnostic (bright solid CTA band on a
  dark game background) so the greyed `Loading ad...` variant is caught while Play-Store end cards are
  rejected; `wait_for_board()` also requires a running clock.
- Run 006 started (max 50) from the board-50 win panel.

### 2026-11-16 16:50: P007 - the board behind a rewarded ad can expire before we see it
- Run 006: won board 1, tapped `Watch Ad -> Play Again`; the ~80 s creative + slow ad polls let the
  *next* board's 60 s clock run behind the end card. The run captured it with **3 s left**
  (`boards/20261116_164254_current_screen.png`), spent 19 taps, got TIME_UP and logged it as a win.
- Fixes: `clock_is_critical()` red-timer guard (never tap a red-clock board, log it `expired`),
  post-tap win confirmed via the UI tree (TIME_UP is a timeout, not a win), no self-repair on a red
  board, `wait_for_board()` rejects red-clock boards.
- Perception on that board was correct (LEP (0,0), POT (1,3), cost 11) -> no annotation needed.
- Run 007 started with `--wait 30` on the Time's Up panel (zero taps until a fresh board).

### 2026-11-16 17:05: P007 root cause - the 75 s reward wait, not the polls
- Run 007 replay: the ad's first `AD_STORE` was at **8 s**, i.e. the creative was already over and the
  reward paid; we closed at **72 s**. The game had dealt the next board at payout, so 64 s of its
  60 s clock was spent on an end card. Board 3 was then skipped by the red-clock guard (correct).
- Fix: screenshot-only badge detection (`src/ad_reward.py`). The AdMob overlay reads
  `Reward in N second(s)` while playing and `Reward granted` after payout; edge-map template match
  needs no OCR/UI dump (0.03 s warm) and separates cleanly over 277 archived frames
  (granted 0.977-1.000 / countdown 0.406 / no badge <=0.255 / boards ~-0.02).
- `close_ad()` closes the instant the badge says granted, before the UI dump; `poll_s` 1.2 s.
  Old timing path kept for creatives without a badge.
- Run 008 started with `--wait 60` on the Time's Up panel (zero taps until a fresh board).
