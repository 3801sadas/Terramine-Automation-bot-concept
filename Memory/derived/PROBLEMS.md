# Problems log (runtime)

Rule: record the problem here **before** attempting a fix.
Format: id | date | state | symptom | evidence | status

---

## P001 — 4x4 / variable grid size unsupported (NEW, 2026-11-15)
- **Recorded:** 2026-11-15 21:30 (before any fix)
- **Seen on:** board `Memory/derived/device/board_new_01.png` (Level 1 · Novice, 52 s on the clock)
- **Symptom:** the game now shows a **4x4** board (16 clickable cells, UI-tree bounds 252 px each),
  but the runtime is hard-wired to 6x6:
  - `src/perception_v2.py::perceive()` loops `range(6)` and uses `calibration.json` cell size 167.83
  - `src/perceive...::detect_lep_pot()` scans `range(6)` rows
  - `src/solve_simple.py::solve_simple()` / `path_exists()` bound the DFS with `0 <= nr < 6`
- **Effect:** on a 4x4 board the automator would read garbage tiles, and `screen_state.classify` may
  even say UNKNOWN (it did on the first probe) → the run halts instead of playing.
- **Evidence:**
  - UI dump: 16 clickable ViewGroups `(45,461)-(297,713) ... (801,1217)-(1044,1460)` → 4 columns / 4 rows
  - visual playfield frame: x 45..1035, y 512..1501 (gold border lines at y=503-511 / 1502-1510, x=36-44 / 1035-1043)
  - level header: `Level 1 · Novice`, `0/1000 XP`, clock 52 s
- **Status:** **FIXED** (2026-11-16) — implemented grid-size agnostic pipeline:
  - New `src/tilegrid.py`: `detect_geometry()` reads tile seams from luminance to find N (4,5,6,7,8),
    returns `{n, left, top, cell_x, cell_y}`. `road_sides()` reads 4 edge openings from a gold-road
    mask (thresholds scale with cell size).
  - `perception_v2.py::perceive()` now uses `tilegrid.detect_geometry()`; for 6x6 it keeps the
    exemplar classifier (trained on 6x6 crops), for other sizes it uses `road_sides()`.
  - `solve_simple.py` infers N from grid keys and bounds-checks with `0 <= r,c < N`.
  - `solve_from_image.py` uses `res["geom"]` for tap centres.
  - Verified: 4x4 board (10 taps, path validated) + 6x6 boards (12, 10 taps) all solve correctly.
  - All tests in `src/test_runtime.py` pass.

### Measurements (2026-11-15, board_new_01.png) — use these for the N=4 fix
- UI clickable cells: `x 45/297/549/801/1044`, `y 461/713/965/1217/1460` -> 252 px; tap centres
  `x 171/423/675/922`, `y 587/839/1091/1339`.
- Drawn tile grid: origin **(41,516)**, cell **252** px = frame `(36,503)` + **(+5,+13)**.
  Rows/cols are clipped by the frame, so cells 4 and 16 are ~7 px short.
- Perception: the 6x6 exemplar classifier misreads 4x4 crops. The APK tile art
  `res/drawable-mdpi/assets_images_goldmine_tile{straighth,curve,tjunction,cross,deadend,grass}.png`
  (1024x1024, opaque, resize+rotate) matched at NCC 0.93-0.94 (road tiles) / 0.89-0.91 (grass)
  and agreed with a gold-road arm mask on all 16 cells. Base openings:
  `straighth=NS, curve=ES, tjunction=NEW, cross=NESW, deadend=S, grass=none`.

### Notes for the fix (not yet applied)
- The drawn playfield rect is constant: `(36,503)-(1043,1510)` (6x6 calibration already uses it).
  Cell size = 1007 / N, N = number of clickable cells per axis from the UI tree.
- The clickable cell rects are shifted ~42 px up vs the drawn tiles, so **taps** should use the
  UI-tree bounds, **perception** should use the drawn playfield rect.
- Suspected grid schedule: 4x4 at Novice levels, probably 5x5 then 6x6 at higher levels
  (needs live confirmation).

---

## P002 — board clock keeps running while the agent inspects a screenshot (2026-11-15)
- **Recorded:** 2026-11-15 21:29
- **Symptom:** the 4x4 board was captured with 52 s left; by the time the tile analysis finished the
  UI showed `Time's Up!` (0 s). Any manual/LLM-in-the-loop analysis of a live board is too slow.
- **Effect:** manual solving of a live board is only safe for the first ~60 s; automated play must
  solve from a single screenshot without extra round-trips.
- **Status:** recorded — no fix needed (design constraint); kept as a reminder to always solve from
  the first capture.

---

## P003 — phone locked / stuck dim overlay mid-session (2026-11-15)
- **Recorded:** 2026-11-15 20:30
- **Symptom:** after ~15 min idle the device showed the lock screen over the game; after unlocking,
  a dark dim overlay persisted (screencap nearly black) until the app was bounced.
- **Status:** FIXED (2026-11-12/15) — `device.ensure_awake()` + `run_loop.too_dark()`/`recover_display()`.
  Kept here because the phone had re-locked again today (screen timeout reset), so verify
  `svc power stayon true` at the start of every batch.

---

## P004 - grass vs deadend template margin is thin (2026-11-15)
- **Recorded:** 2026-11-15 (before building the N=4 perception path)
- **Symptom:** with APK-template NCC on 4x4 cells, `grass` scores 0.89-0.91 and `deadend rot0`
  scores 0.87-0.89 on the *same* pure-grass cells -> only ~0.02 margin. A dead-end tile would
  probably still be ranked first (its arm adds signal), but a wrong call flips a whole plan.
- **Effect:** cannot rely on argmax alone for grass/deadend in the 4x4 pipeline.
- **Planned guard:** confirm with the gold-road arm mask (arm coverage at each cell edge); treat
  "no arm above ~0.35 on any edge" as grass, and require an arm on exactly one edge for deadend.
- **Status:** recorded - guard not implemented yet.

---

## P005 — real 4x4 board mis-read as 6x6 (seam detection silently defaults) (2026-11-16)
- **Recorded:** 2026-11-16 15:26 (before any fix)
- **Seen in:** `endless_20261116_073000_001.log` (won board 1, then `no solution` -> halt),
  evidence `Memory/derived/queue/20261116_152053_no_solution.png`
- **Symptom:** a live 4x4 board is classified as BOARD, but `tilegrid.detect_geometry()`
  returns `{'n': 6, ..., 'source': 'default'}` instead of `n=4, source='seams'`.
  Perception then reads the 4x4 playfield on a 6x6 lattice -> garbage grid
  (`LEP=(3,0) POT=(3,5)` with almost all cells empty) -> `solve_and_validate()` -> NO SOLUTION
  -> run_loop queues the image and halts. The board is wasted.
- **Second sighting:** `board_live_02.png` (visually confirmed 4x4: LEP r3c0 on the left,
  POT r3c3 on the right, two vertical gold segments + a bottom curve; a `Time's Up!` panel
  sits below the board). `detect_geometry()` also returns `source='default', n=6` here.
  Earlier I claimed this image was "not a board" — **wrong**; it is a 4x4 board, so the
  default fallback is silent and dangerous.
- **Root cause (hypothesis, to confirm):** the seam detector relies on a full-width luminance
  dip profile; on grass-heavy boards / boards with the Time's Up panel present it finds no
  clean seam set and falls back to the 6x6 calibration without any error signal.
- **Effect:** the automator refuses to play (or plays garbage) on real low-level 4x4 boards,
  which is exactly the level the user keeps seeing.
- **Fix applied (2026-11-16):**
  1. `tilegrid._fit_grid()` no longer requires the detected seams to span nearly the whole
     board: it now accepts the `n-1` **internal** seam lines (`span >= (n-2.2)*s`) and accepts a
     single clean gap when >= 3 candidate seams exist. For 4x4 the internal span is only 2 cells,
     which the old `(n-1.6)*s` check always rejected -> that was the true root cause.
  2. `tilegrid.detect_geometry()` mirrors a single well-fitted axis (`source='seams_x'/'seams_y'`)
     instead of falling back to 6x6 when the other axis is polluted (gold road / Time's Up panel).
  3. `ad_close_loop.looks_like_real_board()` accepts seams_x/seams_y, and as a last resort
     accepts the default geometry only if some N in {4,5,6} finds LEP **and** POT.
  4. `solve_from_image.py` retries N in {4,5,6} on the fixed frame when geometry is `default`
     and keeps the first candidate whose plan validates.
  5. `run_loop.py --wait <minutes>`: on TIME_UP / menu it now polls the screen with **zero taps**
     until a real board appears (still obeys "do nothing on time-up").
- **Verification:**
  - `queue/20261116_152053_no_solution.png` (the wasted board) now reads `n=4, source=seams`
    and solves with **cost 2** (rotate r2c1 and r2c2 once each).
  - `board_live_02.png` detects `n=4` (previously `default/6`).
  - Regression: 4x4 `board_new_01`, `board_live_01`; 6x6 `fresh_01/02/04/05/06/07`,
    `run_01/02/04`; 3 archived boards -> all still solve.
  - `src/test_runtime.py`: ALL TESTS PASSED.
- **Status:** **FIXED** (verified offline; live confirmation pending a fresh board).

---

## P006 — "Loading ad..." Time's Up panel accepted as a live board (2026-11-16)
- **Recorded:** 2026-11-16 15:44 (before any fix)
- **Seen in:** `endless_20261116_073000_004.log`,
  evidence `queue/20261116_154220_no_solution.png`
- **Symptom:** the user tapped `Watch Ad -> Try Again`; while the ad was loading the CTA turned
  grey `Loading ad...`. `looks_like_result()` keys on the **yellow** CTA band in y 1840-1980, so it
  returned False on that frame. `wait_for_board()` then accepted the stale Time's Up board as real,
  the run played it, got no solution and halted.
- **Aggravating factor:** in the Time's Up panel state the board is drawn ~50 px **higher** than the
  fixed playfield frame (measured: gold road tiles at y 968-1213 instead of 1019-1264), so tile
  perception is wrong there even when seams are detected. That state is unplayable by definition.
- **Effect:** a board that is over gets treated as live -> wasted solve attempt + halt; also any
  greyed CTA variant of the result panel would be misclassified.
- **Fix plan:** detect the result panel by its *content* (the red "Time's Up!" / score row text
  band, or a disabled grey CTA of the same width) rather than by yellow colour alone; and in
  `wait_for_board()` require the clock to be running (no `0s` in the timer region) before accepting a
  board.
- **Fix applied (2026-11-16 16:45):**
  1. `looks_like_result()` is now colour-agnostic: a wide solid bright band (any colour) of >=30
     contiguous rows in y 1840-1980, **on a dark game background** (>=30% dark in the band).
     Measured: game result panels 111-row run + 43-60% dark; Play-Store end card 140-row run but
     2% dark (white page, big blue Install button) -> rejected; live boards 0-row run.
  2. `run_loop.wait_for_board()` now requires a **running clock**: two frames 2.2 s apart must
     differ in the header timer region before a board is accepted, so a finished board that is
     still drawn on screen can never be played.
- **Verification:** `looks_like_result` = True on the `Loading ad...` frame, False on
  `ad_puzzle_01.png` (Install end card), False on live 4x4/6x6 boards. `test_runtime.py` ALL PASSED.
- **Status:** **FIXED**.

---

## P007 — rewarded-ad end card lets the next board's clock run out (2026-11-16)
- **Recorded:** 2026-11-16 16:50 (before any fix)
- **Seen in:** `endless_20261116_073000_006.log`, evidence
  `Memory/derived/boards/20261116_164254_current_screen.png` and
  `Memory/derived/device/diag_timeout_01.png`
- **Symptom:** board 1 of run 006 was won, then the win panel's `Watch Ad -> Play Again` was tapped.
  The ad ran ~2 min (75 s creative + Play-Store sheets). The game had already dealt the **next board
  when the reward fired**, and its 60 s clock ran *behind the ad end card*. When the ad closed, the
  run captured that board with **3 s left** (archived `16:42:54`: red timer `3s`, `32 left`).
  The runtime solved it (cost 11, total 19), tapped 19 times, the clock expired, the Time's Up panel
  appeared, and the post-tap check saw a "result panel" -> **false win**. The next iteration read
  TIME_UP correctly and the run parked.
- **Effect:** a board is silently lost (all taps wasted) whenever an ad end card lingers after the
  reward is granted; worse, the loss is logged as a win.
- **Second bug found while diagnosing:** on the Time's Up panel `looks_like_game()` is still True, so
  the post-tap self-repair path could re-solve and tap a dead board.
- **Fix plan:**
  1. `clock_is_critical()` guard: HUD timer is green (fraction >=0.05) when there is time and red
     (>=0.03) at the end. Measured: 58 s -> red 0.000 / green 0.093; 3 s and 0 s -> red 0.062 /
     green 0.005. Never tap a board whose clock is already red.
  2. Post-tap result must be confirmed with the UI tree: a `TIME_UP` panel is a timeout, not a win.
  3. Never run the residual self-repair on a red/expired board.
  4. `wait_for_board()` must also reject red-clock boards.
- **Fix applied (2026-11-16 16:55):**
  1. New `ad_close_loop.clock_is_critical()` guard (red fraction >=0.03 and > green fraction in the
     HUD timer region). Verified: 58 s -> False, 3 s -> True, 0 s -> True, 43 s win panel -> False.
  2. `run_loop` BOARD branch: a red-clock board is logged as `expired` and **never tapped**; with
     `--wait` the loop then waits for a genuinely fresh board.
  3. Post-tap win check now confirms a result panel with the UI tree: if `classify()` says
     `TIME_UP`, the run logs `expired_mid_plan` (timeout) instead of counting a win, and never runs
     the residual self-repair on it.
  4. `wait_for_board()` rejects red-clock boards too (both the first and the confirmation capture).
- **Verification:** `src/test_runtime.py` ALL TESTS PASSED; timer guard matrix above.
- **Known limitation (not fixed, cost > benefit for now):** the rewarded creative can run ~80 s and
  each ad poll pays for a `uiautomator dump` (~5-15 s), so the loop may notice the fresh board only
  ~50 s after the reward dealt it. With the guard, such a board is skipped cleanly instead of being
  played to a false win; a future improvement is to look for a strong visual X before dumping in
  the close phase.
- **Status:** **FIXED** (guard + false-win). Board-loss window on very long ads remains known.

### P007 follow-up (2026-11-16): close the ad the moment the reward is paid
- **The real cause of the board loss** was not the guard but the fixed `reward_wait=75 s`: the reward
  is paid when the *creative* ends, the game deals the next board immediately, and the end card then
  sits there. Run 007's ad reached its end card at **8 s** (first `AD_STORE` poll) and we closed at
  **72 s** - 64 s of the new board's 60 s clock spent staring at an end card.
- **Fix:** `src/ad_reward.py` matches the ad SDK's badge in the screenshot. It reads
  `Reward in N second(s)` while the video plays and `Reward granted` the instant the reward is paid.
  Matching runs on an *edge map*, so it is colour- and polarity-invariant (white-on-grey and
  black-on-white creatives both score 1.000) and needs no OCR and no `uiautomator dump`.
  `close_ad()` now checks it right after each screenshot, **before** the dump, and closes as soon as
  it is true (>= 4 s after the ad opened); the old timing path stays as a fallback for creatives that
  do not show the badge.
- **Measured separation over 277 archived ad frames:** `Reward granted` 0.977-1.000;
  `Reward in 1 second` 0.406-0.408; ads with no badge 0.085-0.255; game boards -0.014 to -0.024.
  Threshold 0.55 sits in a wide gap. Cost per poll: 0.03 s warm.
- **Poll cadence** also tightened: `poll_s` 2.5 -> 1.2 s and post-tap settle 3.0 -> 1.2 s, so the
  worst-case reaction to the badge flip is ~2 s instead of 5.5 s.
- **Verification:** `src/test_runtime.py` - new `test_reward_granted_fast_close` closes at 5 s with
  `reward_wait=75`, and `test_reward_wait` proves a countdown badge is still never tapped early.
  ALL TESTS PASSED.
- **Status:** **FIXED (offline-verified)** - pending a supervised live run.

---

## P008 - badge detector does not cover the Play-Store end-card ads (2026-11-16)
- **Recorded:** 2026-11-16 17:25 (before any fix)
- **Seen in:** `endless_20261116_073000_008.log`, board lost right after `Watch Ad`
- **Symptom:** board 2 was won, `Watch Ad` was tapped, and the ad ran the full 75 s. The badge fast
  path never fired (`rewarded creative playing -> waiting (3s .. 69s/75s)` is the old fallback path),
  so the next board was picked up with a red clock and skipped by the red-clock guard. The board was
  lost exactly like P007.
- **Why the badge did not fire:** this creative is a *different network* - at close time it is a
  full-screen "Twin Tales / ENSAPIA" Google-Play-style end card with only a top-left `X`
  (`ad_close/samples/20261116_165550_current_screen.png`, from run 007; run 008 served the same ad).
  There is no `Reward granted` badge anywhere, so `ad_reward.reward_state()` correctly returns
  False for the whole ad and the code falls back to the 75 s wait.
- **Reward timing estimate:** the board is dealt when the reward is paid. Run 007 closed at 72 s and
  the board had ~3 s left -> dealt at ~15 s; run 008 closed at ~75 s and the board was already red
  -> same ballpark. So this ad pays out in its first ~10-15 s and then parks on the end card for
  another minute, opening the Play Store 1-3 times on the way.
- **Missing evidence:** no frames of this creative's *playing* phase are kept, so the
  reward moment cannot be identified from the archive. `save_sample()` only stores the frame where a
  close tap happened, which is already the end card.
- **Fix plan:**
  1. Capture every ad-poll frame (small, derived) so the next occurrence of this creative can be
     analysed frame by frame.
  2. From those frames, add a screenshot-only end-of-creative detector that covers ad networks with
     no badge (video freeze / end-card layout), while never closing a *playable* ad before its
     reward (those show the badge instead, so the two rules must not overlap).
  3. Keep the red-clock guard as the last line of defence.
- **Status:** recorded - collecting frames before fixing.

### P008 fix (2026-11-16, operator rule change)
- **Rule change:** the operator has decided the reward is to be treated as already confirmed, so the ad
  must be closed **earlier** instead of waiting for a badge or a 75 s timer.
- **Change:** `close_ad()` gained `early_close_s` (default **18 s**). At that point it stops waiting
  and closes the ad with the normal X detection, whether or not any badge was seen. The badge fast
  path (`Reward granted`) still closes even sooner (>= 4 s), a frozen end card still closes early,
  and `reward_wait` (75 s) is now only an absolute safety cap. Every poll also logs the badge score.
- **Why 18 s:** in both measured board losses (runs 007, 008) the game dealt the next board ~15 s into
  the ad, so 18 s leaves ~50 s of the 60 s clock. Tunable via the `early_close_s` argument.
- **Frame capture (diagnostic, kept on):** every ad poll now saves a downscaled JPEG, the UI-tree XML
  and a JSON line (elapsed, badge score, static counter) under
  `Memory/derived/ad_close/runs/<timestamp>/`, so the next unknown creative can be analysed offline.
  `AD_CAPTURE=0` disables it; the offline tests run with it off.
- **Verification:** `src/test_runtime.py` ALL TESTS PASSED, including the new
  `test_early_close_no_badge` (Twin Tales end card, no badge anywhere -> closes at 17 s instead of 75).
- **Status:** **FIXED (offline-verified)** - pending a supervised live run.

---

## P009 - the "early close" tapped ad content instead of closing (2026-11-16)
- **Recorded:** 2026-11-16 17:45 (before any fix)
- **Seen in:** `endless_20261116_073000_011.log`, board lost again right after `Watch Ad`
- **Symptom:** with `early_close_s=18` the ad still took ~70 s and the board behind it was already
  at **0 s** when the ad finally closed (`device/after_stop_011.png`). Boards 1 and 2 were won;
  `900/1000 XP`, `32 left`.
- **Frame evidence** (`ad_close/runs/20261116_173511/`, 13 polls, montage
  `ad_close/debug/montage_run011.png`): the `Watch Ad` tap started a **chain of three creatives**
  - `poll 1-3` Shacom Bank end card (0-13 s),
  - `poll 4` Play Store sheet (closed correctly),
  - `poll 5-10` K Cash creative (18-48 s),
  - `poll 11-13` Blade War creative (54-70 s), which is the first frame to show a real `X`.
- **Why the close did not happen at 18 s:** at 18 s (`poll 5`) the creative **had no close widget at
  all**. The UI trees prove it: `content-desc="Close"` appears only in `poll_13.xml`
  (`android.widget.Button`, bounds `[36,117][108,189]`, i.e. top-left (72,153)); polls 1-12 contain
  no close element whatsoever.
- **What the code did instead (the actual bug):** `_pick()` fell back to remembered
  `known_point` coordinates after poll 5, so it blindly tapped `(975,584)` twice (inside the video)
  and `(1007,152)` twice (on the AdChoices **info** icon). Those taps cannot close anything, and the
  `(1007,152)` ones sit next to `Install` / ad content - a violation of the "never tap ad content or
  Install" rule. The ad only closed at poll 13, when a real `Close` widget finally existed.
- **Teardown:** the run was killed at poll 14 (before it could touch the dead board), so the board
  was abandoned rather than mis-played.
- **Fix plan:**
  1. Never blind-tap remembered coordinates on an ad. Only tap a *visually confirmed* close glyph
     (score >= 0.70, corner regions) or a *UI-tree* `Close` widget.
  2. When the deadline is due and no close widget exists, use `KEYCODE_BACK` instead: the ad runs
     in its own activity, so BACK dismisses it without touching ad content. The reward is treated as
     already confirmed (P008 operator rule), so BACK is acceptable.
  3. Keep the red-clock guard as the last line of defence.
- **Status:** recorded - implementing the fix now.

---

## P010 - the run loop died on a transient screenshot, losing a live board (2026-11-16)
- **Recorded:** 2026-11-16 19:45 (before any fix)
- **Seen in:** `endless_20261116_073000_012.log`, `__stderr_012.txt`
- **Symptom:** a live 40 s board was on screen and the loop crashed instead of playing it.
- **Cause:** `device.screenshot()` raised `ValueError("black frame")` on a transient blank
  `screencap` (common right after an ad closes or the display wakes), and the exception
  propagated out of `wait_for_board` and killed the whole process.
- **Fix:** `device.screenshot()` retries **4×** with growing backoff (0.8/1.6/2.4/3.2 s) and
  only raises after the last attempt. All call sites in `run_loop.py` (main loop, both
  `wait_for_board` captures, post-tap win check) now go through `_shot_or_recover()`, which
  recovers the display and retries instead of dying.
- **Verification:** syntax ok; `test_runtime.py` ALL TESTS PASSED.

---

## P011 - the multi-ad interstitial chain has no early exit (2026-11-16)
- **Recorded:** 2026-11-16 20:30 (before any fix)
- **Seen in:** `ad_close/runs/20261116_194433/` (run 013), montage `ad_close/debug/montage_run013.png`
- **Symptom:** `Watch Ad` starts a chain of **three** creatives that only yields at the end:
  - poll 1-5 (0-20 s) K Cash - no close widget
  - poll 6 (25 s) Play Store sheet (K Cash) - `Close` in UI tree returns to the **next** ad
  - poll 7-8 (30-35 s) Shacom Bank - no close widget
  - poll 9 (40 s) Play Store sheet (Shacom) - `Close` → next ad
  - poll 10-12 (47-65 s) Blade War - no close widget
  - poll 13 (65 s) Blade War end card - **X at top-left**, closes at poll 14
- **BACK does nothing here:** the three BACK presses (18-35 s) landed inside the WebView and just
  navigated the ad. This network is not a dismissible activity; it is a stack.
- **Consequence:** the board behind such an ad is dead regardless of close speed - the reward is
  paid when `Watch Ad` is tapped (board dealt immediately, ~65 s chain), so the board's 60 s clock
  always expires. The 18 s early-close rule cannot help here; P009's no-blind-tap guard is the
  correct behaviour.
- **Contrast:** the AdMob-style creative (youtube.com, `Reward granted` badge) **does** close
  cleanly: detector scored 1.00, closed at poll 7, board returned with **38 s** left
  (`device/after_ad_close.png`). The badge path works when the ad has a badge.
- **Untested hypothesis (deferred):** BACK on a *Play Store sheet* may exit the whole stack
  rather than returning to the next ad. Would need one live AD_STORE to find out.
- **Status:** recorded - no code change; the no-blind-tap guard stands.

---

## P011 fix - BACK on every Play Store sheet accelerates the exit (2026-11-16)
- **Recorded:** 2026-11-16 20:50 (after the live test)
- **Hypothesis tested:** BACK on a Play Store sheet exits the whole ad stack. **Falsified** - the
  next poll came back `AD_WEBVIEW`, so it just navigated inside the ad like any other BACK.
- **What actually worked:** pressing BACK **early and repeatedly**. Run 016's timeline:
  - poll 3 (13 s) Play Store sheet -> BACK
  - poll 4-5 (18 s) no close widget -> BACK x2
  - poll 6 (~18 s) board visible -> closed
  - **board returned at 46 s** (vs 5 s in run 014, where we only pressed Close)
- **Change:** `close_ad(back_on_store=True)` sends BACK on the first Play Store sheet, and the
  existing 18 s deadline then fires the remaining BACKs. `run_loop.py` passes `back_on_store=True`
  on both ad entry points. Close on a confirmed X still takes priority.
- **Measured effect:** ad close ~18 s instead of ~65 s; board clock 46 s instead of 5 s.
- **Verification:** `test_runtime.py` ALL TESTS PASSED.
- **Status:** **FIXED (live-verified)**.

---

## P012 - Level 12 (Apprentice) boards misperceived, plans returned `unknown` (2026-11-16)
- **Recorded:** 2026-11-16 22:45 (before any fix)
- **Seen in:** `endless_20261116_073000_019.log`, boards 37-38
- **Symptom:** two consecutive boards returned `unknown` instead of `win`. Board 39 came back
  with a red clock and was skipped.
- **Board 37** (`boards/20261116_223805_current_screen.png`, 42 s, Level 12):
  LEP is visibly at **bottom-left (3,0)** and POT at bottom-right (3,3), but the solver reported
  `lep=[0,0] pot=[3,3] base=16 total=24` — wrong LEP, 24 taps on a mostly-empty board. The plan
  was applied and the board did not reach a result state.
- **Board 38** (`boards/20261116_223818_current_screen.png`, 86 s, Level 12): LEP/POT looked
  correct at (0,0)/(3,3) but the plan came back `base=0 total=8` — a degenerate plan that also
  failed to win.
- **Why:** Level 12 is the first `Apprentice` tier the pipeline has played much; the tile
  rendering (grass vs road contrast, LEP sprite placement) differs enough from Novice 4x4 boards
  that the arm-reader / LEP detector misreads. Not an ad problem, not a solver problem.
- **Fix plan:** collect the two failed frames (already archived above) and re-run perception on
  them offline to find the misread, then retrain/adjust the LEP/POT reader for the Apprentice
  tile set.
- **Status:** recorded - diagnosing perception on Level 12.

---

## P013 - mistake taps spend the whole budget, then the "Out of moves!" overlay is
##        treated as a fresh board (2026-11-17)
- **Recorded:** 2026-11-17 18:40 (before any fix)
- **Seen in:** `endless_20261116_073000_021.log`, boards 41-42; earlier boards 25/26 too.
- **Symptom:** board ends `unknown` after two residual repairs; the next "board" is the
  same dead board.
- **Evidence (board 41/42, `boards/20261117_182948_current_screen.png`):**
  - 18:29:48 frame: **80 s left, 20 moves left**, LEP (0,0), POT (1,3). Perception was
    **correct**; no ad was involved.
  - Solver plan: `base=12 + 8 mistake taps = 20 total` - exactly the entire move budget.
  - 18:30:49 frame (`..._183049_current_screen.png`): same board at **0 moves**, "Out of
    moves!" overlay. The loop classified it `BOARD (visual)` and tapped a further 9-tap plan.
- **Why:** two independent defects compound:
  1. the intentional wrong-then-fix mistakes are real moves, so a plan can consume every
     remaining move; the final fix tap lands on the overlay (or the last rotation never
     registers) and the board is dead unwon;
  2. `screen_state.classify()` checked the Board rules (text `Tap road tiles...`, `Level`,
     `XP`, `N left`, board cells) **before** the Out-of-moves rule, and the dead board is
     still visible behind the overlay - so the overlay was read as a live board.
- **Fix:**
  - `screen_state.classify`: Out-of-moves is now checked at 0c, before the board rules.
  - `run_loop`: reads `moves_left` before solving; if `plan.total >= moves_left` it re-solves
    with `--no-mistakes`, and if it still cannot leave headroom it does not tap at all and
    waits for a fresh board.
  - `test_runtime.test_classify`: new `OUT_OF_MOVES_XML` (board markers + overlay) asserts the
    overlay never classifies as BOARD.
- **Status:** **FIXED**; ALL TESTS PASSED.

---

## P014 - a board captured with ~20 s left dies to a single dropped tap (2026-11-18)
- **Recorded:** 2026-11-18 20:45 (before any fix)
- **Seen in:** `endless_20261118_201058_001.log`, board 61 (Level 24, 5x5)
- **Run:** 31 boards, 30 wins. The loss ended the run: loop parked on Time's Up, waited
  120 s, halted, supervisor restarted into another Time's Up.
- **Symptom:** `plan: lep=[4,0] pot=[2,4] base=18 total=26` -> no repair log -> `unknown`,
  then Time's Up.
- **Evidence:** `boards/20261118_203319_current_screen.png` (the re-solve frame) shows
  **15 s** left and the board still unconnected. The first capture (`..._203315`) was ~20 s.
  Offline re-solve of the same frame reproduces `COST 18 +8 = 26` exactly, so perception
  and the plan were right - the board simply ran out of clock.
- **Why:** the board was dealt during the ad chain, so only ~20 s of its 60 s clock
  survived. The loop then spent that margin on work that is not taps:
  - the `suspicious plan -> re-capturing` branch costs ~2 s sleep + screenshot + solve;
  - the plan carried **8 intentional mistake taps** on a 47-move budget, ~1 s of taps;
  - after the taps, the residual repair (subprocess solve + screenshot + taps) needs ~4 s,
    and at that point the clock hit 0 - it never got to run.
- **Fix plan:**
  - add `low_clock(img)`: the HUD timer turns **amber** late in the board (measured
    15 s -> orange 0.104 / green 0.005; 37-80 s -> orange 0.028-0.030 / green 0.09-0.11),
    same pixel-region approach as `clock_is_critical`;
  - on a low clock: never take the 2 s re-capture branch, and re-solve with
    `--no-mistakes` so the plan carries no decorative taps;
  - log why a residual repair was skipped instead of failing silently.
- **Fix (applied):**
  - `ad_close_loop.low_clock()` - amber-timer detector on the same HUD region
    (orange >= 0.06 and orange > 2*green).
  - `run_loop`: on a low clock it solves with `--no-mistakes` and skips the 2 s
    re-capture branch; residual-repair skips are now logged instead of silent.
  - `test_runtime.test_low_clock`: 15 s frame -> True, 80 s frame -> False, and
    15 s is still not `clock_is_critical`.
- **Status:** **FIXED**; ALL TESTS PASSED.
