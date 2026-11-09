# Club World Cup with 32 clubs (experimental Phase 1)

Opt in with the recipe-level boolean `"cwc32": true`; omitted or false preserves the
existing competition. There is no GUI switch. A recipe with no new leagues may enable it.
Plan reports the format, and saved plans/recipes preserve the setting through rebuilds.
Use a fresh career to test changes to competition structure.

## Generator and build contract

`tools/mkcwc.py` exposes `reshape(regs, ko=200, log=print)` (new bytes, input unchanged,
`ValueError` on incompatible templates or collisions) and
`build(base, out=None, ko=200, dry=False, log=print)` (table IO). The CLI remains:

```
python tools/mkcwc.py --base <pesdb dir> --out <livecpk root> [--ko 200] [--dry]
```

`--dry` needs no output directory and writes nothing. A standalone custom `--ko` prints a
warning: the native runtime must be compiled with the same `CWC_KO`. Mod Studio always uses
200, matching `tools/native/fl26swiss.c`; it does not expose a configurable knockout ID.

Competition 1 keeps its identity, entries and all twenty language names. Regulation 1 becomes
the Libertadores group template (regulation 9, competition 5), eight groups of four played
once, with replicas 1025, 2049 ... 8193. Regulation 200 is the original CWC knockout template
expanded to sixteen clubs, with its third-place playoff disabled: 48 group matches plus
15 single-leg knockout matches, 63 in total. Extra time and penalties remain enabled. Other regulation rows are preserved byte for byte.

Build generates CWC after the European, domestic and continental competition generators and
before competition renaming/world-file export. ID 200 is reserved when enabled in league
planning, split phase allocation, European qualifiers, national/super cups, continental cups
and helper competition allocation (including rebuild pins). Base-table conflicts and previous
league/cup owners fail explicitly; enabling CWC never silently relocates a career-held ID.
Existing slot maps already exclude 200 from some pools; the explicit reservation protects
against future map changes. Disabled recipes pass empty reservations and skip the generator.

`fl26world.py` needs no new world-file directive: CWC is detected by the native runtime from
the generated rows. The runtime already implements entrants, group draw/registration,
progression, fixed dates and July teardown. No native binary changes are required in Phase 1;
the installed module must contain that existing CWC implementation. Python source builds
import the generator directly; verify it is included when packaging a frozen application.

## Limits and compatibility

This is an annual experimental 32-team format, not the complete real-world tournament.
The source currently dates the groups on days 153/154, 157/158, 161/162 and knockout on
165/166, 169/170, 173/174, 177/178 (June); the old prototype note saying December was stale.
There is no four-year cadence, history/ranking cycle, realistic continental qualification,
new pot system, calendar conflict solver, GUI change or continental cup rework.
Entrants still come from the native fixed league-table access list and fallback pools.

FL27 needs separate in-game verification: its patched executable chains existing hooks
(including native UEFA handling), and CWC relies on the same record layouts, draw, progression,
dating and teardown hooks. Changed CWC/Libertadores templates or occupied IDs are rejected
at plan/build time. Passing offline table tests does not prove those runtime hooks work,
that the field is full, or that its June dates fit every league calendar.
The historical prototype note reports one private two-season run; this contribution makes
no new in-game validation claim.

## Regression and next in-game checks

```
python tools/test_cwc32.py
python tools/test_cwc32.py <folder with game pesdb tables>
git diff --check
```

The first command uses synthetic tables; the second also exercises actual plan/build,
recipe round trips, rebuilds, a split/national cup and disabled parity in a temporary game
folder. No real game world is installed or activated.

On FL26 and FL27 separately, start fresh careers with CWC enabled and disabled. Capture
module versions and logs; verify 32 distinct entrants, eight groups, three games per club
(48 group matches), correct top-two bracket handover, 15 knockout matches with no
third-place fixture, a valid final, dates, standings and Competition Info pages. Save/reload before draw,
during groups and before knockout; advance across July teardown and a second season.
Check league/continental date conflicts and compare the disabled CWC with the stock world.


## CWC rules correction after the first FL27 test

The user-reported first run confirmed 32 entrants, groups of four, three group matches per
club, two advancing and a knockout of sixteen. It also exposed inherited template rules.
The corrections below are offline-verified; a new in-game run is still required.

### Third place: a real fixture flag, not just text

The four-team CWC template has `CompetitionRegulation +0x10` bit 28 set. The parser at
`0x1414f8125` in the inspected FL27 executable sends it through setter `0x1414c9b30` to
runtime `+0x304` bit 9. Fixture builder `0x1413f49f0` tests it at `0x1413f4d70` and, if set,
emits the extra fixture with kind `0x36`. A second builder, `0x1413f4f90`, tests it at
`0x1413f50af` and skips kind `0x36` if clear. The Rules page reads the same flag at
`0x140a9d34d`. So the old prototype requested a functional bronze game, not merely a label.

`mkcwc.reshape` clears bit 28 only in the newly generated knockout (normally ID 200).
Its sixteen-club field, format 35, extra time and penalties are retained. Leg subtype
(`+0x10` bits 9-11) is zero and bit 29 is set, as in the original single-match CWC:
8 round-of-16 games + 4 quarterfinals + 2 semifinals + 1 final = 15 matches.
No other competition loses its third-place match.

No native change is required. `cwc_progress` still supplies sixteen clubs and starts the
same knockout ID. `cwc_dates` supplies borrowed date records; those are calendar capacity,
not match count. Its World Cup date template can include bronze dates, but the fixture
builder checks **CWC's own** third-place flag before creating the bronze match. Keep the
existing native date array until the next run confirms final scheduling; do not delete
calendar records or truncate a shared World Cup template to force a match count.

### Group wording: two independent fields had disagreed

The prototype changed rounds (`+0x10` bits 12-14) from two to one but retained Libertadores'
leg subtype 1 (`+0x10` bits 9-11). The parser maps the latter to runtime `+0x300` bits 29-31.
The group Rules description at `0x140a9b6d0` calculates three matches using the round count
but chooses different text at `0x140a9bab2` according to that independent subtype. This is
why the screen could display both three matches and home-and-away wording.

CWC now clears that subtype on its master and all eight replicas, matching the shipped
single-meeting group format. Other group fields, names and all shared translations stay
unchanged. Verify the resulting wording in the next run; no translation or format-enum
replacement has been made.

### Away goals in the standings list: not the knockout away-goals flag

The generated group rows already have `+0x10` bit 24 clear. That bit controls the functional
two-leg away-goals decider (`0x14133191e` calls `0x14151bf40`); clearing it again cannot fix
this standings description. The knockout explicitly keeps it clear too.

On this FL27 build the group ranking-description routine `0x140a9bc80` selects a complete
text entry using runtime `+0x2f8` (patch at `0x1426da530`, table at `0x142668d20`). CWC inherits
policy 7 from its Libertadores template (`+0x10` bits 5-8). This is also the calendar/season
policy field: changing it for a different description is not a proven cosmetic-only edit.
FL27 overrides that text selector to policy 4 specifically for competitions 2 and 3, not CWC.

The observed away-goals line is therefore generic policy-selected Rules text, **not proof
that away goals currently decide a tied CWC group**. The group's actual tie comparator has
not been fully traced or exercised with controlled tied results. We cannot honestly label
its away-goals criterion functional or inert from this screen alone. No safe independent
CWC-only switch for that criterion has been established, so this field and the ordering
algorithm are deliberately unchanged; tests protect the inherited policy from accidental
edits. Full FIFA 2025 tie-break fidelity remains an explicit limitation, not a completed fix.

[FIFA's 2025 regulations](https://digitalhub.fifa.com/m/18848e4224efbd91/original/FCWC25_Regulations_EN.pdf),
articles 12-14, require 63 matches without third place, head-to-head points/difference/goals
first for tied groups, then reapplication to remaining tied teams, overall difference/goals,
conduct and lots. Reusing the World Cup's policy would not establish that complete ordering.

For the next test use a **new world name and a new career**, not an existing season whose
fixtures/rules may already be saved. Check that Rules has no bronze game and single-meeting
group wording; count actual fixtures as 48 + 8 + 4 + 2 + 1, and ensure the final produces a
winner, including extra time/penalties when needed. Save/reload before each knockout round
and verify the final survives July cleanup. For group ordering, capture each tied team's
points, head-to-head scores, overall and away goals before/after reload. A two-team drawn
head-to-head tie with equal overall goal difference/goals but different nominal away-goals
counts is useful evidence; several controlled cases are needed before attributing the
result to away goals or claiming full FIFA ordering.
