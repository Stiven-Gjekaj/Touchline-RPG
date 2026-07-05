# Touchline RPG — v1 Architecture & Build Plan

## Context

The repo is a completely empty greenfield project (zero files, zero commits, locally or on the remote). The goal is a text-based football career-mode RPG: create a young player, progress season by season through training, matches, transfers, and aging, aiming for glory. The original framing was "website now, desktop later," but the user has since decided to skip straight to a desktop-first build: a Python backend serving a local webpage, opened in a native-feeling window rather than deployed as a multi-user site. This plan defines a concrete, buildable v1 vertical slice — not a platform for hypothetical future features (club finance sims, international duty, deep tactics, AI-vs-AI transfer markets are explicitly deferred).

**Confirmed product decisions:**
1. Desktop-first: Python backend + local web UI, no deployed multi-tenant site.
2. No accounts/auth — single local save, but multiple save *slots* (like classic save files).
3. Fully fictional world (generated leagues/clubs/players) — sidesteps IP/licensing entirely.
4. Match simulation is stat-driven summary (score + key events + recap text), not minute-by-minute play-by-play.
5. One implementation detail was left to engineering judgment rather than re-asking: whether the "local webpage" opens in the user's browser or a wrapped native window. **Recommendation: pywebview, with automatic fallback to opening a browser tab if pywebview's OS dependency isn't available.** Flagging this clearly since it's the one default not explicitly confirmed by the user.

---

## 1. Tech Stack

| Concern | Choice | Why |
|---|---|---|
| Web framework | **Flask** (sync, no async) | Single local client, CPU-bound work (simulate a match, run a query), HTML forms not JSON APIs. FastAPI's strengths (async, OpenAPI, Pydantic JSON validation) target a shape this app doesn't have. Flask's `render_template`, `flash()`, and htmx pairing fit a server-rendered text app better. |
| Frontend | **Jinja2 templates + htmx + Pico.css** (vendored static files, no Node/npm) | "Text-based" UI is tables/recaps/forms, not a full SPA. htmx adds partial-page updates (Advance Week, Play Match, training, transfer responses) via `hx-*` attributes without a JS build pipeline. Pico.css makes semantic HTML look decent with zero markup changes. Routes should branch on the `HX-Request` header to render either a partial or the full page wrapping it — same template either way. |
| Desktop wrapper | **pywebview**, fallback to `webbrowser.open()` | Wraps the local Flask server in a real native window using the OS's own web engine (WebView2/WebKit/WebKitGTK) — one pip dependency, no bundled Chromium/Node. Packages cleanly with PyInstaller later. Avoids the "which browser tab is the app" confusion of a manual-browser approach. Caveat: Linux needs system WebKitGTK (not pip-installable) and Windows needs the WebView2 runtime (near-universal on modern Windows but not guaranteed) — wrap the launch in `try/except` and fall back to opening a browser tab against the same local server if the native window fails. |
| Persistence | **SQLite via SQLAlchemy, one `.sqlite` file per save slot** | Domain is inherently relational (leagues→clubs→players→contracts→matches). SQLite gives ACID crash-safety with zero extra services. One file per slot maps directly onto "save slot" as a game concept. No Alembic in v1 — store a `schema_version` int in a `meta` table; on mismatch, tell the user the save is incompatible rather than migrating (schema will churn too much pre-1.0 for migrations to pay off). Use `platformdirs.user_data_dir(...)` for the save directory (overridable via env var for tests) — critical so a future PyInstaller bundle doesn't break on paths relative to `__file__`/cwd. |
| Engine purity / testability | `engine/` package has **zero imports** of Flask/SQLAlchemy/pywebview; all randomness goes through an injected `random.Random`, never the global `random` module | This is what makes the whole game simulatable and unit-testable with plain dataclasses and no app/DB/HTTP context. `persistence/` is the only package importing SQLAlchemy, translating ORM rows ↔ engine dataclasses via mapper functions. `web/` routes stay thin: load via repository → call engine function(s) → persist → render. |

**Dependencies (deliberately short):** `flask`, `sqlalchemy`, `pywebview`, `platformdirs`, `pytest` (dev). htmx + Pico.css are vendored static files.

---

## 2. Project Structure

```
Touchline-RPG/
├── run.py                        # entry point: python run.py (thin shim -> desktop.launcher.main)
├── pyproject.toml
├── README.md                      # setup instructions incl. Linux WebKitGTK note
├── .gitignore                     # saves/*.sqlite, __pycache__/, .venv/
├── saves/                         # dev-mode default save dir (gitignored)
├── touchline/                     # import root
│   ├── config.py                  # save-dir resolution (platformdirs + env override), constants, version
│   ├── engine/                    # PURE domain + game logic — zero Flask/SQLAlchemy/pywebview imports
│   │   ├── models.py               # dataclasses: Player, Club, League, Country, Season, Match,
│   │   │                           #   MatchEvent, MatchPlayerStat, Contract, TransferOffer, Position enum
│   │   ├── constants.py            # POSITION_WEIGHTS, tier means/spreads, xG constants, calendar weeks
│   │   ├── generation.py           # world/league/club/player/name generation
│   │   ├── scheduling.py           # round_robin_pairings / double_round_robin
│   │   ├── simulation.py           # poisson(), team_strength(), simulate_match(), recap text
│   │   ├── progression.py          # apply_training(), apply_decline(), check_retirement()
│   │   ├── transfers.py            # interest probability, offer generation, negotiation state machine
│   │   ├── career.py               # advance_week(), run_end_of_season(), promotion/relegation
│   │   └── rng.py                  # weighted_choice, clamp, gauss helpers around random.Random
│   ├── data/                       # first_names.json, last_names.json, club_name_parts.json
│   ├── persistence/                 # the ONLY package importing SQLAlchemy
│   │   ├── db.py                     # engine/sessionmaker factory bound to a save file path
│   │   ├── orm_models.py             # SQLAlchemy declarative models mirroring engine.models
│   │   ├── mappers.py                # to_domain()/from_domain()
│   │   ├── repositories.py           # PlayerRepository, ClubRepository, SeasonRepository, TransferRepository...
│   │   └── save_manager.py           # list/create/delete save slots, reads each save's meta row
│   ├── web/                          # thin Flask layer
│   │   ├── __init__.py                # create_app() factory
│   │   ├── active_save.py             # holds currently-loaded save's session
│   │   ├── routes/                    # saves.py, dashboard.py, season.py, match.py, player.py, club.py, transfers.py
│   │   ├── templates/                 # base.html + per-route folders + partials/ (htmx fragments)
│   │   └── static/                    # css/pico.min.css, css/app.css, js/htmx.min.js (vendored)
│   └── desktop/
│       └── launcher.py                # Flask-in-thread + pywebview window + browser fallback
└── tests/
    ├── conftest.py                    # seeded rng, tmp save dir, sample club/player builders
    ├── engine/                        # test_generation/scheduling/simulation/progression/transfers/career.py
    ├── persistence/                   # test_repositories.py, test_save_manager.py
    └── web/                           # test_routes_smoke.py
```

`touchline/desktop/launcher.py` sketch (binds `127.0.0.1` only — this is local-only, never a network service):
```python
import socket, threading, webbrowser

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def main() -> None:
    from touchline.web import create_app
    app = create_app()
    port = _free_port()
    t = threading.Thread(
        target=lambda: app.run(host="127.0.0.1", port=port, debug=False,
                                use_reloader=False, threaded=True),
        daemon=True,
    )
    t.start()
    url = f"http://127.0.0.1:{port}"
    try:
        import webview
        webview.create_window("Touchline RPG", url, width=1200, height=800, min_size=(900, 600))
        webview.start()
    except Exception:
        webbrowser.open(url)
        t.join()
```
(`use_reloader=False` is required — Werkzeug's reloader forks/re-execs, which breaks when Flask runs on a background thread inside another process.)

---

## 3. Core Domain Model

Attributes are ints on a 0-99 scale (FIFA/FC-card-familiar). Six shared attributes cover every position (`goalkeeping` near-zero for outfield players) — one uniform schema instead of subclassing.

- **Position** (enum): `GK, DF, MF, FW` — broad for v1; richer sub-positions are an additive v1.1 extension.
- **Player**: `id, first_name, last_name, age, position, nationality, club_id (nullable), pace, shooting, passing, defending, physical, goalkeeping, potential, form (-10..+10), morale (0-100), condition (0-100), injury_weeks_remaining, is_user, is_retired, contract_id`. `overall()` is computed on the fly (position-weighted sum, §4a), never stored.
- **Club**: `id, name, short_name, league_id, division_tier, reputation, wage_budget`. Squad is a relationship via `Player.club_id`. `wage_budget` bounds plausible offers — not a full finance sim.
- **Country**: `id, name` — single row for v1, modeled as its own entity so multi-country is additive later.
- **League**: `id, name, tier, country_id, promotion_slots, relegation_slots` (symmetric across adjacent tiers so club-count-per-division stays constant).
- **Season**: `id, year_label, current_week, is_complete`. Fixtures are `Match` rows — no separate "Fixture" entity.
- **Match**: `id, season_id, week_number, home_club_id, away_club_id, home_goals (nullable), away_goals (nullable), is_played`.
- **MatchEvent**: `id, match_id, minute, event_type (GOAL/YELLOW_CARD/RED_CARD/INJURY/KEY_PASS/SAVE), club_id, player_id (nullable), description`.
- **MatchPlayerStat**: `id, match_id, player_id, goals, assists, rating (1.0-10.0), minutes_played, was_injured`. Stored only for the user's player (every match) and any player involved in a notable event league-wide (supports a cheap top-scorers table) — not for all ~720 players every week.
- **Contract**: `id, player_id, club_id, wage_per_week, signed_on_week, expires_on_week`.
- **TransferOffer**: `id, player_id, from_club_id, to_club_id, offer_fee, wage_offered, length_offered_years, status (PENDING_CLUB_DECISION | REJECTED_BY_CLUB | PENDING_USER_DECISION | COMPLETED | WITHDRAWN), week_created`.
- **SaveGame meta**: one row per save file's own SQLite db: `id=1, save_name, created_at, last_played_at, schema_version, current_season_id, current_week, user_player_id, user_club_id`. The save-select screen scans `saves/*.sqlite` and briefly opens each to read this row — no separate registry file to drift out of sync.

---

## 4. Core Algorithms

### 4a. Procedural generation

Scope: **1 fictional country, 3 tiers, 12 clubs/tier = 36 clubs**, ~20-player squads (~720 players). 12 clubs gives a clean 22-week double round-robin.

Position attribute weights (each row sums to 1.0; drives both `overall()` and generation skew):

| Position | pace | shooting | passing | defending | physical | goalkeeping |
|---|---|---|---|---|---|---|
| GK | 0.05 | 0.00 | 0.15 | 0.10 | 0.20 | 0.50 |
| DF | 0.15 | 0.05 | 0.15 | 0.40 | 0.25 | 0.00 |
| MF | 0.15 | 0.15 | 0.35 | 0.20 | 0.15 | 0.00 |
| FW | 0.30 | 0.35 | 0.15 | 0.05 | 0.15 | 0.00 |

```python
def overall(player) -> int:
    w = POSITION_WEIGHTS[player.position]
    return round(sum(getattr(player, attr) * weight for attr, weight in w.items()))
```

Tier strength distribution, plus a per-club offset so clubs within a tier vary:

| Tier | mean overall | spread (std dev) |
|---|---|---|
| 1 (top) | 70 | 8 |
| 2 | 58 | 8 |
| 3 | 46 | 8 |

```python
club_offset = clamp(gauss(0, 4), -10, 10)   # once per club
target_overall = clamp(gauss(tier_mean + club_offset, spread), 20, 95)   # per player

def generate_attributes(position, target_overall, rng):
    weights = POSITION_WEIGHTS[position]
    avg_weight = sum(weights.values()) / len(weights)
    attrs = {}
    for attr, w in weights.items():
        skew = (w - avg_weight) * 100
        raw = target_overall + skew + rng.gauss(0, 6)
        attrs[attr] = int(clamp(round(raw), 1, 99))
    return attrs
```

**Potential**: age < 21 → `clamp(target_overall + randint(5, 25), target_overall, 99)` (generous headroom, occasional wonderkids); age ≥ 29 → potential ≈ target_overall. Same headroom curve drives progression (§4d).

**Squad composition**: ~20 players/club, ~2-3 GK / 6-7 DF / 6-7 MF / 4-5 FW. **Age**: `clamp(gauss(25, 4), 16, 38)`.

**Name generation**: curated static word lists (`first_names.json`, `last_names.json`, few hundred entries each) combined by random pairing (200×300 → 60,000 combos). Club names: `prefix + suffix` (e.g. "North"+"ham") + a club-suffix bank ("United", "City", "Athletic", ...) → "Northham United"; reroll on collision.

**User's player**: short create-flow (name, position), age 16-18, modest overall (~40-50) with generous potential headroom, placed into a bottom-tier-ish club's squad — a "rags to riches" opening.

### 4b. Match simulation

**Starting XI**: fixed shape 1 GK + 4 DF + 4 MF + 2 FW (no tactics system in v1 — deliberately deferred), best-`overall()` available non-injured players per position group; fill from best remaining outfield players if a group is short.

**Team strength → scoreline**, independent Poisson per side (same family as real xG-based prediction models):
```python
BASE_XG = 1.35
SCALE_FACTOR = 40       # rating-point gap that shifts xG by 1.0
HOME_ADVANTAGE = 4

home_strength = mean(overall(p) for p in home_xi) + HOME_ADVANTAGE
away_strength = mean(overall(p) for p in away_xi)
diff = home_strength - away_strength
home_xg = max(BASE_XG + diff / SCALE_FACTOR, 0.15)
away_xg = max(BASE_XG - diff / SCALE_FACTOR, 0.15)
home_goals = poisson(home_xg, rng)
away_goals = poisson(away_xg, rng)
```
```python
def poisson(lam, rng):   # Knuth's algorithm, no numpy needed
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1
```
Constants are playtesting starting points, not claimed as calibrated (sanity-checked: 85-vs-45 → home_xg≈2.35/away_xg≈0.35; 5-point gap → 1.475/1.225).

**Goal attribution** (guarantees attributed goals sum to team score; hat-tricks emerge naturally):
```python
def attribute_goals(squad, n_goals, rng):
    weights = {p.id: goal_share_weight(p) for p in squad if not p.injury_weeks_remaining}
    return [weighted_choice(weights, rng) for _ in range(n_goals)]
# goal_share_weight: FW = shooting*1.0 + pace*0.3; MF = shooting*0.6 + passing*0.3; DF = shooting*0.2; GK ≈ 0
```
Assists: ~65% of goals get one, weighted-choice by `passing` (excluding the scorer).

**User's player influence**: indirectly via the XI-average strength calc, directly via the same goal/assist rolls, plus a personal rating:
```python
rating = 6.0 + 0.8*goals + 0.5*assists
rating += 0.3 if team_won_big else (-0.3 if team_lost_big else 0)
rating += gauss(0, 0.4)
rating = clamp(round(rating, 1), 1.0, 10.0)
```
Injury roll: ~2-4% base per match, reduced by `physical`/`condition`; severity tiers minor(1-2wk)/medium(3-6)/severe(8-16), weighted toward minor. Cards: ~10% yellow/~1% red, nudged by `defending`+position — flavor only in v1 (no minute-by-minute consequences).

**Recap**: sort `MatchEvent`s by minute, render via template strings, append scoreline + user's personal line.

**Scope control**: all 36 clubs' matches simulate every week (cheap; needed to keep standings/promotion accurate), but only the user's match gets full treatment (ratings, full events, recap). The other ~17 run a fast path (scoreline + goal attribution for league tables + lightweight injury/card roll), skipping per-player ratings nobody will see.

### 4c. Season / fixture scheduling

Round-robin via the circle method:
```python
def round_robin_pairings(n_teams):
    teams = list(range(n_teams))
    fixed, rotating = teams[0], teams[1:]
    rounds = []
    for round_num in range(n_teams - 1):
        opponent = rotating[-1]
        pairing = [(fixed, opponent) if round_num % 2 == 0 else (opponent, fixed)]
        others = rotating[:-1]
        for i in range(len(others) // 2):
            a, b = others[i], others[-(i + 1)]
            pairing.append((a, b) if round_num % 2 == 0 else (b, a))
        rounds.append(pairing)
        rotating = [rotating[-1]] + rotating[:-1]
    return rounds

def double_round_robin(n_teams):
    first_half = round_robin_pairings(n_teams)
    second_half = [[(away, home) for home, away in rnd] for rnd in first_half]
    return first_half + second_half   # 2*(n_teams-1) weeks; 22 for 12 clubs
```
The `round_num % 2` flip avoids the fixed team being home every round of the first half. Test invariants directly rather than trusting hand-derived index math: each club appears exactly once per round; every pair meets exactly once per half; each pair meets exactly twice total with one home/away each.

**Season calendar** (30-week cycle, then repeat with ages +1 and fixtures regenerated from new divisions):

| Weeks | Phase | Activity |
|---|---|---|
| 1-3 | Preseason | Training only; transfer window OPEN |
| 4-25 | Regular season | 22 match weeks, all 3 divisions simultaneously |
| 26 | Season end | Standings finalized, promotion/relegation, retirements, contract expiries, youth intake |
| 27-30 | Offseason | Training + transfer window OPEN (primary window) |

```python
def advance_week(save):
    phase = calendar.phase(save.current_week)
    if phase == MATCH:
        play_all_fixtures_for_this_week(save)
        apply_post_match_effects(save)
    else:
        apply_training_week(save)
    if calendar.is_window_open(save.current_week):
        roll_transfer_interest(save)
    save.current_week += 1
    if save.current_week > SEASON_LENGTH:
        run_end_of_season(save)
```

**Promotion/relegation**: sort each division by (points, GD, GF); bottom `relegation_slots` of tier T swap with top `promotion_slots` of tier T+1; regenerate next season's fixtures from new memberships. Test invariant: `promotion_slots(T+1) == relegation_slots(T)` so each division's club count (12/12/12) stays constant. Bottom tier has no relegation.

**Youth intake**: at end-of-season, any club whose squad drops below ~18 after retirements gets 1-2 freshly generated young players (age 17-20, tier-appropriate, via the §4a generator) — keeps the league alive indefinitely without simulating an AI transfer market.

### 4d. Attribute progression

**Training** (non-match weeks; user picks a focus — Attacking/Playmaking/Defensive/Physical/Balanced/Rest; NPCs auto-pick based on position):
```python
def apply_training(player, focus, rng):
    if player.age >= 30:
        return apply_decline(player, rng)
    headroom = player.potential - overall(player)
    if headroom <= 0:
        return
    base_chance = clamp(headroom / 100, 0.05, 0.9)
    age_factor = 1.5 if player.age <= 21 else (1.0 if player.age <= 25 else 0.5)
    for attr in ATTRS_BOOSTED_BY[focus]:
        if rng.random() < base_chance * age_factor / len(ATTRS_BOOSTED_BY[focus]):
            gain = rng.choice([1, 1, 2])
            setattr(player, attr, clamp(getattr(player, attr) + gain, 1, 99))
```
Match minutes give a smaller supplementary growth roll on the attribute most exercised by the player's position — playing time matters for development, not just training focus, so benching a prospect has a real cost.

**Decline** (age ≥ 30): `decline_chance = clamp((age-30)*0.05, 0, 0.6)`, per-attribute, pace/physical decline first/fastest, passing/defending held longer.

**Retirement**:
```python
def check_retirement(player, rng):
    if player.age < 33: return False
    if player.age >= 41: return True
    base = clamp((player.age - 32) * 0.12, 0, 1)
    modifier = -0.3 if overall(player) >= 70 else (0.2 if overall(player) < 45 else 0)
    return rng.random() < clamp(base + modifier, 0.02, 0.95)
```
**The user's player is exempt from this silent auto-roll.** Losing your own character without warning is bad UX — instead surface a warning once decline risk becomes material (e.g. age 33+), let the user choose when to retire (triggering a career-summary screen), with a hard floor (forced retirement only if overall drops below ~30 while age > 35).

### 4e. Transfer logic

Deliberate v1 scope limit: **only the user's player participates in the transfer market** — AI clubs don't trade among themselves (squads change only via aging/retirement/youth-intake). A full AI-to-AI market is complexity most playtime won't notice.

Interest rolled weekly against ~5-10 reputation-plausible suitor clubs (not all 35):
```python
probability = BASE_RATE * performance_factor * attribute_fit_factor * contract_factor * reputation_fit_factor
probability = clamp(probability, 0, 0.15)   # per-club, per-week ceiling
```
- `performance_factor`: recent match ratings + season goals/assists vs. position norms.
- `attribute_fit_factor`: is the player an upgrade at that position for the suitor club?
- `contract_factor`: boosted as contract nears expiry, boosted more if already a free agent.
- `reputation_fit_factor`: tolerance band around current club reputation (big clubs don't chase far below their level).

**Valuation**: `fee ≈ overall² × age_curve(age) × (0.5 + potential/200) × TIER_VALUE_SCALE`, `age_curve` peaking ~24-27; wage pitched above current to entice; shorter contract lengths for older players. Starting constants to tune via playtesting.

**Negotiation** (a state machine, not a mini-game): `PENDING_CLUB_DECISION` → club evaluates (reputation gap, squad importance, contract closeness) → `REJECTED_BY_CLUB` (terminal) or `PENDING_USER_DECISION` → user accepts (`COMPLETED`: updates club_id, closes old contract, opens new one, logs history), rejects (`WITHDRAWN`), or counters wage once (re-rolled against a fair ceiling, capped at 1-2 rounds).

**Windows**: reuse the season calendar (§4c) — `is_window_open(week)` gates only *new* offer creation (weeks 27-30, optionally 1-3); existing pending offers can be answered any time.

---

## 5. Build Order / Milestones

Engine (generation → simulation → scheduling → progression) is built and fully unit-tested with **zero web/persistence code** first — proves the "pure, UI-agnostic core" property concretely rather than aspirationally. Web UI is then built against **in-memory** state first (fastest path to something clickable, isolates "does Flask drive the engine right" from "does the DB round-trip right"), with real persistence retrofitted once the interaction shape is proven.

- **M0 — Scaffolding**: package skeleton, `pyproject.toml`, pytest wired up, `run.py` prints hello (no Flask yet). *Verify: `pytest` green, `python run.py` runs clean.*
- **M1 — Domain models + generation** (`engine/models.py`, `generation.py`): dataclasses, name banks, league/club/player generation. *Verify: tier-ordering of average overalls, squad size/positional bounds, name uniqueness.*
- **M2 — Match simulation** (`engine/simulation.py`): Poisson helper, strength calc, goal/assist attribution, rating, recap text. *Verify: seeded exact-value regression test; "strong beats weak in ≥70% of 1000 trials"; attributed-goals-sum-to-score invariant.*
- **M3 — Scheduling + season loop** (`scheduling.py`, `career.py`): round-robin, weekly tick, promotion/relegation. *Verify: round-robin invariants; full-season headless sim test asserting standings math and promotion/relegation correctness.*
- **M4 — Progression + retirement** (`progression.py`): training growth, decline, retirement. *Verify: young/high-potential overall non-decreasing until potential hit; old player trends down; potential ceiling respected. Extend M3's soak test to 20+ seasons — no exceptions, no squad collapse (validates youth intake).*

  *— engine complete: the whole game is simulatable headlessly, fully tested, no web/DB code yet —*

- **M5 — Web UI skeleton, in-memory state**: app factory, base template + Pico.css, create-player flow, dashboard, standings/fixtures, play-match + recap, squad view, training-focus screen — full core loop clickable in a browser, backed by one ephemeral in-memory `Career` object. *Verify: `test_client()` smoke tests for 200s + key strings; manual click-through of a full season.*
- **M6 — Persistence**: `orm_models.py`, `mappers.py`, `repositories.py`, `save_manager.py`, `meta`/`schema_version`, save-slot screens (new/list/load/delete); wire routes to load-at-start/persist-after-each-action. *Verify: round-trip repository tests; manual test that quitting mid-career and relaunching resumes exactly, two slots persist independently.*
- **M7 — Transfers** (`transfers.py` + inbox/negotiation UI), against the real persistence layer. *Verify: directional unit tests (higher performance/lower reputation-gap ⇒ higher interest); negotiation state-machine coverage of every path; manual playtest through a full accepted and a full rejected negotiation.*
- **M8 — htmx pass**: `hx-*` attributes on Advance Week / Play Match / training / transfers, `HX-Request` branch in routes, vendor `htmx.min.js`. *Verify: existing `test_client()` tests pass unchanged; manual check the UI feels snappier.*
- **M9 — Desktop wrapper**: `desktop/launcher.py` (Flask-in-thread + pywebview + browser fallback), `run.py`. *Verify: native window opens on this dev environment's OS (Linux/WebKitGTK); flag Windows/macOS each need their own manual smoke pass since webview behavior is platform-native.*
- **M10 — Polish**: styling pass, recap/flavor text pass, name-bank expansion, edge-case hardening, README with setup + Linux caveat.

---

## 6. Verification Approach

**Unit tests (`tests/engine/`)** — deterministic (seeded `random.Random`, regression-style) where an exact value is meaningful, statistical (many trials + threshold) where the formula is inherently probabilistic:
- Generation: tier-average ordering across seeds, squad-size/position bounds, name uniqueness.
- Simulation: seeded exact-value regression case; strong-beats-weak trial test; goal-attribution-sums-to-score invariant; rating always in `[1.0, 10.0]`.
- Scheduling: round-robin invariants parametrized over club counts (10/12/14).
- Career: headless multi-season soak test — standings recomputed independently must match the engine's own table; promotion/relegation preserves per-division counts; no unhandled exceptions across 20+ seasons.
- Progression: monotonic growth/decline trends; potential ceiling respected; retirement probability monotonic in age.
- Transfers: directional interest-probability checks; valuation sanity bounds; every negotiation state-machine path covered.

**Persistence tests (`tests/persistence/`)**: build via engine functions → persist via repository → reload → assert field-by-field equality, against a `tmp_path`/in-memory SQLite per test (never the real save directory).

**Web tests (`tests/web/`)**: Flask `test_client()` via `create_app()` pointed at a temp save dir; assert status codes + key rendered strings. No Selenium/Playwright — disproportionate for a server-rendered text app.

**Manual end-to-end playtest checklist** (after each relevant milestone):
1. `python run.py` — native window opens (or browser fallback engages).
2. Create a career — assigned to a bottom-tier-ish club with sensible starting attributes.
3. Play a full season week by week — recaps match the box score; standings match hand-recomputed points/GD; training lets you pick a focus and attributes move; an injured player sits out and recovers on schedule.
4. End of season — promotion/relegation applied correctly; next season's fixtures reflect new divisions.
5. Quit mid-career, relaunch — resumes exactly where left off (validates per-action persistence, not just on-exit).
6. Create a second save slot — both persist independently, load screen lists both correctly.
7. Fast-forward several years — young players grow, 30-somethings decline and eventually retire (user's own player gets the retirement *choice*, not silent auto-retirement); transfer offers arrive for a standout player; complete both an accepted and a rejected negotiation.
8. Cross-platform spot check — verify pywebview on this dev environment's OS at minimum; Windows/macOS each need their own manual pass since webview behavior is platform-native.

Optional low-cost addition: a minimal `.github/workflows/tests.yml` running `pytest` on push (cheap, pure upside even solo).
