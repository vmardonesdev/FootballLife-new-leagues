# CONCACAF Champions Cup engine

The dedicated Python generator, native handover and Lua contract loader are implemented
and tested offline. **FL27 in-game playability is not yet verified.**
Target `13`, code `FL_CONCACAF`, the existing name, logo overrides and saved primary
competition/regulation pins remain its identity. There is no format selector or second cup.
New plans never pad/truncate it into the former 16-team knockout. Build rejects legacy plans,
enabled feeder modules and incompatible packaged runtimes before writing staging files.
The standalone `mkccup.py` CLI also refuses `FL_CONCACAF`. Other continental generators
retain their existing behavior. Already installed worlds and careers are not edited.

## Recipe and plan

An existing `europe`/`game_europe` assignment to target 13 requests the modern plan.
Alternatively this top-level block requests it without explicit domestic assignments:

```json
{
  "concacaf": {
    "modules": {
      "leagues_cup": false,
      "central_american_cup": false,
      "caribbean_cup": false
    },
    "sources": {
      "liga_mx": ["My Mexican League"],
      "mls": [166]
    }
  }
}
```

Source overrides are optional, ordered lists of regulation ids or new league names.
Use the ids in the actual database; 166 above is only an example. Available domestic cup
ids are mapped to symbolic `cup:<league regulation>` sources. The pure planner also
accepts these symbolic ids. League roles are `liga_mx`, `mls`, `canadian_premier`;
cup roles are `canadian_championship`, `us_open_cup`, `liga_mx_champion`, `mls_cup`.
Regional sources belong to their module and cannot be overridden as domestic sources.
Unknown, foreign-association or unavailable explicit sources are errors.

The adapter discovers top divisions by actual table countries/confederations, not a fixed
MLS regulation id. Country classification provides default domestic roles; use overrides
where a database has more than one top division. It only exposes domestic cups already
available through the existing home-cup architecture. It does not invent an MLS Cup or
an Apertura/Clausura champion resolver. When a separate champion source is unavailable,
the league's first ranked eligible club is the documented direct-berth proxy. A future
native adapter must supply the actual champion result before claiming sporting fidelity.

`tools/concacaf.py` owns validation, source ordering, quotas and the qualification contract.
`plan()` stores a versioned `concacaf` object with 27 source places, not a fixed club list;
the ordinary `ccups` list holds a pending descriptor with an empty generic `entry` list.
Recipe settings round-trip independently of this derived object. `resolve()` is a pure
reference resolver for previews/tests; it is **not called by the game**. The native adapter
executes the equivalent domestic-source contract. Build marks the generated descriptor
runtime-ready only after table generation; that marker is not an in-game validation claim.

## Places and module combinations

| Pathway | Places | Direct Round of 16 |
|---|---:|---:|
| Liga MX | 6 | 1 |
| MLS | 5 | 1 |
| Leagues Cup | 3 | 1 |
| Central American Cup | 6 | 1 |
| Caribbean Cup | 3 | 1 |
| Canadian Premier League | 2 | 0 |
| Canadian Championship | 1 | 0 |
| US Open Cup | 1 | 0 |

All five direct places are reserved before the 22 Round One places. Round One has eleven
two-leg ties; eleven winners join the five direct clubs. Round of 16, quarterfinals and
semifinals have two legs; the final has one. No defending Champions Cup winner is added.

| Leagues | Central | Caribbean | Regional-result sources | Redistributed places |
|---|---|---|---|---:|
| off | off | off | none | 12 |
| on | off | off | Leagues | 9 |
| off | on | off | Central | 6 |
| off | off | on | Caribbean | 9 |
| on | on | off | Leagues, Central | 3 |
| on | off | on | Leagues, Caribbean | 6 |
| off | on | on | Central, Caribbean | 3 |
| on | on | on | all three | 0 |

Every row still plans exactly 27 places, 22 Round One and five direct. Leagues Cup requires
both MLS and Liga MX sources; the other two modules are independent. Enabling a module
only declares a future result source: no regional tables, fixtures or competitions are generated.
**Only the first row can currently build.** Enabled feeder modules are rejected explicitly
until their completed-result providers exist; they are never replaced by invented winners.

## Qualification policy

* **Disabled module:** its quota and direct berth use domestic standings from that region.
* **Unavailable domestic pathway:** use the same regional replacement policy; an explicitly
  configured but unavailable source is a validation error rather than a silent substitution.
* **Enabled, incomplete result in later seasons:** raise `QualificationPending`; wait, retain
  the source and do not treat it as disabled.
* **Enabled, missing or invalid later result:** clear validation error requiring repair.
* **First season only:** absent/incomplete results use league entry order as a seed ranking;
  absent cup/regional results use regional domestic fallback. Explicitly invalid results still
  fail. This policy must not be reused for subsequent seasons.
* **Duplicate qualification:** advance through the relevant source's ranked eligible clubs,
  then use regional fallback if its ranking is exhausted. The same club never takes two places.

Fallback exhausts same-region leagues before other CONCACAF leagues. Within a region,
it considers rank one across leagues, then rank two, etc., with country and source id providing
a deterministic order. A club outside eligible domestic memberships is rejected. Completed
league results must include the whole current membership; enabled regional results must
contain at least their quota of eligible, unique clubs. Replacement rankings should include
additional finishers where available. The reference resolver conservatively requires completed
rankings for all leagues considered together in a regional fallback tier.

Each resolution starts with an empty used-club set. Current memberships and fresh completed
results can be supplied each season without modifying the plan. Known memberships are
deduplicated when checking capacity; unbuilt leagues contribute symbolic capacity until
club ids exist. Such capacity is provisional: actual qualification must still validate exactly
27 unique eligible clubs and fail if it cannot fill them. No partial or expanded field is valid.

## Migration and career safety

Explicit legacy target-13 positions are retained as preferred source/rank references within
their modern geographic quotas. A domestic cup rank zero becomes its cup-winner source.
Conflicting enabled-module assignments, repeated references, unavailable sources and quota
overflow fail for review instead of dropping places. Old recipes that explicitly assign more
than six Liga MX or five MLS places consequently need redistribution. A plan with saved
recipe settings retains those settings. In older plans without settings, former automatic MLS
padding cannot reliably be distinguished from explicit assignments: ambiguous padding is
not promoted into twelve new explicit berths. Review those recipes before eventual Build.

Primary pins under `cup_ids["ccup:FL_CONCACAF"]` are carried forward. The technical helper
uses `cup_ids["concacaf:FL_CCC_R1"]` through the shared allocator. Offline Build/rebuild tests
retain both identities, including after adding a league and its national cup.
Every modern plan carries `requires_new_career: true`; there is no safe in-place migration of
a career containing the old bracket. Build rejects old target-13 plans as well. Existing installed
legacy worlds can continue unchanged; this work neither inspects nor rewrites their saves.

## Generator and runtime

`mkconcacaf.generate()` copies the established mode-1 UEFA knockout (two legs except
the final), fixes its field to sixteen and clears the bronze-match bit. Other scoring rules
remain those of the established templates; this milestone verifies structure and progression,
not a complete sporting-rule audit. It rejects
an unexpected template instead of guessing. The helper uses CONMEBOL's
`mkeuropo.prerounds_single(..., one_match=False)` with eleven ties: master plus eleven
replicas, within the twenty-table limit. It does not change ordinary eight-tie preliminaries.
Static primary membership contains a preview of all 27 unique clubs; runtime selects anew.

`fl26concacaf.h` contains the bounded contract parser, pure qualifier resolver, match-pair
counter and strict handover validator. The adapter in `fl26swiss.c` retains five byes and
22 preliminary clubs in the existing save/user/date-scoped checksummed state journal
(synthetic final-table key `0xfffd`). It registers the helper using the existing master-first,
replica-fallback path. Match ownership may be the master or replicas: every live record
is counted once by its actual two clubs. All eleven ties must each have exactly two
scheduled matches, no unplayed matches, and an actual game winner belonging to that
tie. Seeded/provisional winners are never used. The sixteen-team field is validated before
installation; five ties pair a bye with a winner, followed by three winner-versus-winner ties.

Completed domestic results are captured before teardown through the existing retained
tables/cup-winner storage. Later qualification requires retained completed results; live
mid-season standings and strength seeds are not substitutes. Retention lasts 330 days;
the first summer alone permits entry-order fallback. An incomplete used source waits;
missing later results produce an explicit qualification error. The season snapshot is
resolved against current domestic memberships: departed clubs are excluded, returning
clubs retain their completed relative ranking and promoted/new clubs follow in entry order.
This ordering supplies eligible replacements without treating a running season as final.
The snapshot is
invalid after July rollover or when loading an earlier save. Qualifier/year flags are reset,
and the next edition resolves sources afresh. A new-career build marker is required for
first-season fallback. The main knockout remains in the existing cup registry, so existing
champion retention and July teardown apply without adding a defending-winner place.

Build emits `ccup` (main calendar/lifecycle), `lpre` (helper/calendar) and
`concacaf 1 data=<comma-separated uint16 words>`. Generic filling of these two regulations
is intercepted by the dedicated engine; their legacy `entry=` lists are registry placeholders,
not alternative qualification instructions. The packed layout is documented alongside
`cq_parse()` in `fl26concacaf.h`: version/ids/dates, domestic source records and 27 place
records containing preferred source/rank references and regional fallback lists. It contains
no permanently qualified club ids. Source indexes are zero-based. Unknown versions,
truncation, invalid counts and unavailable source ids are rejected.

Lua checks `fl26_swiss_concacaf_version()` before installing hooks, then loads the contract
after cup/preliminary registration. Native acceptance requires the club-list, progression,
teardown and daily hooks. Build checks the packaged PE exports and ABI data without loading
the DLL; Switch on checks the installed DLL and Lua before changing the world or INI.
Required exports: `fl26_swiss_concacaf`, `fl26_swiss_concacaf_version`,
`fl26_swiss_concacaf_abi` (value 1). Old world files without this directive retain old behavior.

## Calendar and FL27 validation

The 365-day calendar uses fill day 243 (1 September), Round One days 33/40 (3/10 February),
R16 61/68 (3/10 March), QF 89/96 (31 March/7 April), SF 117/124 (28 April/5 May), and
final day 145 (26 May). There are nine distinct dates with at least seven days between
rounds: **51 matches**, including one final and no bronze match. The main calendar borrows
the seven-record Libertadores knockout, avoiding FL27's extra UEFA play-off records.
All source/fallback domestic leagues reserve both preliminary days and seven main days
through the existing shared rest/calendar scheduler. This is static spacing and runtime
conflict avoidance, not proof that an arbitrary congested world has no fixture collisions.
Check actual domestic cups, league matches and any other continental commitments in game.
If handover misses the first R16 date, the runtime logs an error instead of dating it in the past.

Build the native module with `tools/native/build-swiss.sh <output DLL>` (Zig), or on Windows:

```powershell
gcc -shared -O2 -fno-builtin-logf -o out/concacaf-engine/fl26swiss.dll tools/native/fl26swiss.c -lkernel32
```

Package this DLL with this branch's `sider/experimental/fl26swiss.lua`. Rebuild the normal
module pack using `tools/lbpack.py <new output directory>`; verify its Lua was not selected
from an older sibling public checkout. Do not overwrite an existing development pack without
retaining it. Build refuses a stale pack even if a newer DLL exists elsewhere in the repository.

For the next game test, install matching modules into a **separate FL27 test installation**,
build a new isolated world with all three modules false, activate through Switch on, and
start a new ML career. Never activate this structure over a legacy career. Preserve the Sider
log and the state journal belonging to the test save. Verify the contract-accepted line,
27 unique qualifier lines (five direct), 22 preliminary fixtures and their dates, no R16 after
first legs, the all-22-complete handover line, 16/8/4/1 main matches and a single final.
There must be 51 completed fixtures total. Reload before/after qualification and before/after
the last second leg; confirm no duplicate registration. Cross July, verify helper/main teardown,
champion retention and a fresh field derived from the next season's completed sources.
Check missing/incomplete-source errors, domestic collision logs, and Competition Info's helper
presentation. No new Mod Studio UI or native helper-page alias is implemented in this milestone.
No FL27 in-game validation was performed during development.

## Tests

Run `python -m unittest discover -s tools -p 'test_concacaf*.py'`. Set `CONCACAF_TEST_BASE`
to a folder containing the game's tables to include actual recipe planning and round trips
for all eight combinations, plus isolated table generation and fake-game Build/rebuild tests.
Set `CONCACAF_TEST_DLL` to the compiled DLL to include compatibility/build tests.
`tools/native/test_concacaf.c` exercises strict completion, winners, match counting, duplicate
rejection, contract bounds and season resets without any game pointers.
Also run the existing `test_pinned_ids.py` and `test_conmebol_modern.py` with that database
path. The latter builds unrelated CONMEBOL worlds in a temporary fake game directory.
