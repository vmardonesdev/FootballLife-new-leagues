"""CONCACAF Champions Cup qualification contract; no table or runtime generation.

Source ids are regulation ids (strings in JSON), or symbolic future sources. A source
catalogue describes leagues/cups, never a permanent continental field. resolve() is a
reference implementation for tests and previews, not a substitute for native qualification.
"""
import copy

TARGET, CODE, NAME = 13, "FL_CONCACAF", "CONCACAF Champions Cup"
FORMAT = "concacaf27"
MODULES = ("leagues_cup", "central_american_cup", "caribbean_cup")
QUOTAS = {"liga_mx": 6, "mls": 5, "leagues_cup": 3, "central_american_cup": 6,
          "caribbean_cup": 3, "canadian_premier": 2, "canadian_championship": 1,
          "us_open_cup": 1}
DIRECT = ("liga_mx", "mls", "leagues_cup", "central_american_cup", "caribbean_cup")
REGIONS = ("north", "central", "caribbean")
PATH_REGION = {p: "north" for p in QUOTAS}
PATH_REGION.update(central_american_cup="central", caribbean_cup="caribbean")
CHAMPIONS = {"liga_mx": "liga_mx_champion", "mls": "mls_cup"}
ROLES = set(QUOTAS) | set(CHAMPIONS.values())
CENTRAL = {"belize", "costa rica", "el salvador", "guatemala", "honduras", "nicaragua", "panama"}
NORTH = {"mexico", "usa", "united states", "united states of america", "canada"}
BUILD_BLOCKED = ("CONCACAF Champions Cup requires the dedicated 27-team generator and runtime contract v1; "
                 "the generic cup generator cannot build it. Re-plan the recipe and start a new career.")


class QualificationError(ValueError):
    pass


class QualificationPending(QualificationError):
    """Wait for the source's season to finish; do not redistribute its places."""


def region(country):
    country = country.strip().lower()
    return "central" if country in CENTRAL else "north" if country in NORTH else "caribbean"


def configuration(raw=None):
    if raw is None:
        raw = {}
    if not isinstance(raw, dict) or set(raw) - {"modules", "sources"}:
        raise QualificationError("concacaf must be an object with modules and/or sources (no format selector)")
    modules = raw.get("modules", {})
    sources = raw.get("sources", {})
    if not isinstance(modules, dict) or set(modules) - set(MODULES):
        raise QualificationError("concacaf.modules supports " + ", ".join(MODULES))
    if any(type(v) is not bool for v in modules.values()):
        raise QualificationError("CONCACAF module switches must be true or false")
    if not isinstance(sources, dict) or set(sources) - ROLES:
        raise QualificationError("concacaf.sources has an unknown qualification pathway")
    for role, refs in sources.items():
        if not isinstance(refs, list) or any(type(r) not in (int, str) or not str(r).strip() for r in refs):
            raise QualificationError("CONCACAF source %s must be a list of regulation ids or new league names" % role)
        if role in MODULES:
            raise QualificationError("regional source %s is managed by its module, not a domestic override" % role)
    return {"modules": {k: modules.get(k, False) for k in MODULES}, "sources": copy.deepcopy(sources)}


def catalogue(rows):
    out = {}
    for value in rows:
        if not isinstance(value, dict) or type(value.get("id")) not in (str, int) or not str(value["id"]).strip():
            raise QualificationError("CONCACAF source needs a nonempty id")
        s = copy.deepcopy(value)
        key = str(s["id"])
        if key in out or s.get("conf") != 6 or s.get("region") not in REGIONS:
            raise QualificationError("CONCACAF source %s must be unique and belong to CONCACAF with a known region" % key)
        if s.get("code") == CODE:
            raise QualificationError("the defending Champions Cup winner is not a qualification source")
        if s.get("kind") not in ("league", "cup"):
            raise QualificationError("CONCACAF source %s must be a league or a cup" % key)
        capacity = s.get("capacity", 0)
        if type(capacity) is not int or capacity < 0 or (s["kind"] == "league" and not capacity):
            raise QualificationError("CONCACAF source %s has no valid capacity" % key)
        teams = s.get("teams")
        if teams is not None and (not isinstance(teams, list) or len(teams) != capacity
                                  or any(type(t) is not int or t <= 0 for t in teams)
                                  or len(set(teams)) != len(teams)):
            raise QualificationError("CONCACAF source %s has an invalid seed membership list" % key)
        s["id"] = key
        s.setdefault("roles", [])
        if not isinstance(s["roles"], list) or any(r not in ROLES for r in s["roles"]):
            raise QualificationError("CONCACAF source %s has invalid roles" % key)
        out[key] = s
    return out


def source_order(sources, geographical_region):
    """Same-region leagues first; stable ids, independent of recipe row order."""
    return sorted((k for k, s in sources.items() if s["kind"] == "league"),
                  key=lambda k: (sources[k]["region"] != geographical_region, sources[k]["region"],
                                 sources[k].get("country", ""), k))


def plan(raw, rows, legacy=(), previous_ids=None):
    config = configuration(raw)
    sources = catalogue(rows)
    roles = {role: sorted(k for k, s in sources.items() if role in s["roles"]) for role in ROLES}
    for role, refs in config["sources"].items():
        refs = [str(r) for r in refs]
        if len(refs) != len(set(refs)) or any(r not in sources for r in refs):
            raise QualificationError("CONCACAF source %s names an unavailable or repeated source" % role)
        expected = "cup" if role in {"canadian_championship", "us_open_cup"} | set(CHAMPIONS.values()) else "league"
        if any(sources[r]["kind"] != expected or sources[r]["region"] != "north" for r in refs):
            raise QualificationError("CONCACAF source %s must use North American %s sources" % (role, expected))
        country_role = "liga_mx" if role == "liga_mx_champion" else "mls" if role in ("mls_cup", "us_open_cup") else "canadian_premier" if role == "canadian_championship" else role
        countries = {"liga_mx": {"mexico"}, "mls": NORTH - {"mexico", "canada"}, "canadian_premier": {"canada"}}
        if any(sources[r].get("country", "").lower() not in countries[country_role] for r in refs):
            raise QualificationError("CONCACAF source %s belongs to the wrong domestic association" % role)
        roles[role] = refs
    if config["modules"]["leagues_cup"] and (not roles["liga_mx"] or not roles["mls"]):
        raise QualificationError("Leagues Cup requires both MLS and Liga MX league sources")

    # Capacity is exact for known memberships; new clubs use symbolic places until Build
    # assigns their ids. Runtime must still check actual membership and exactly 27 clubs.
    eligible = set()
    for key, s in sources.items():
        if s["kind"] == "league":
            eligible.update(s.get("teams", [(key, i) for i in range(s["capacity"])]))
    if len(eligible) < 27:
        raise QualificationError("CONCACAF Champions Cup needs 27 unique eligible clubs; available source capacity is %d" % len(eligible))

    places = []
    for path, quota in QUOTAS.items():
        enabled = path in MODULES and config["modules"][path]
        preferred = ["module:" + path] if enabled else roles.get(path, []) if path not in MODULES else []
        if enabled:
            sources[preferred[0]] = {"id": preferred[0], "kind": "regional", "conf": 6,
                                     "region": PATH_REGION[path], "capacity": quota, "roles": [path]}
        for i in range(quota):
            direct = path in DIRECT and i == 0
            primary = preferred
            rank = i + 1
            if direct and path in CHAMPIONS and roles[CHAMPIONS[path]]:
                primary = roles[CHAMPIONS[path]]
            elif i and path in CHAMPIONS and roles[CHAMPIONS[path]]:
                rank = i
            places.append({"path": path, "place": i + 1, "stage": "round_of_16" if direct else "round_one",
                           "preferred": [{"source": k, "rank": rank} for k in primary],
                           "fallback": source_order(sources, PATH_REGION[path]),
                           "reason": "enabled_module" if enabled else "disabled_module" if path in MODULES
                           else "domestic" if primary else "unavailable_domestic"})

    migrated, seen = [], set()
    for ref in legacy:
        key, rank = str(ref["source"]), ref["rank"]
        if key not in sources or type(rank) is not int or rank < 0:
            raise QualificationError("legacy CONCACAF assignment has no eligible source: %s" % ref)
        s = sources[key]
        if rank == 0:
            key = "cup:" + key
            if key not in sources:
                raise QualificationError("legacy CONCACAF cup winner has no cup source")
            rank, s = 1, sources[key]
        if (key, rank) in seen:
            raise QualificationError("repeated legacy CONCACAF assignment")
        seen.add((key, rank))
        if s["kind"] == "cup":
            path = "canadian_championship" if s.get("country", "").lower() == "canada" else "us_open_cup"
        elif s["region"] == "central":
            path = "central_american_cup"
        elif s["region"] == "caribbean":
            path = "caribbean_cup"
        else:
            path = next((r for r in ("liga_mx", "mls", "canadian_premier") if key in roles[r]), None)
        if not path or (path in MODULES and config["modules"][path]):
            raise QualificationError("legacy CONCACAF place %s conflicts with its modern pathway; review the assignment" % ref)
        if s["kind"] == "league" and rank > s["capacity"]:
            raise QualificationError("legacy CONCACAF rank exceeds source capacity")
        candidates = [p for p in places if p["path"] == path and "legacy" not in p
                      and (p["stage"] != "round_of_16" or rank == 1 or path in MODULES)]
        if not candidates:
            raise QualificationError("legacy CONCACAF places exceed the %s quota; review assignments instead of truncating" % path)
        slot = candidates[0]
        slot["preferred"] = [{"source": key, "rank": rank}]
        slot["legacy"] = copy.deepcopy(ref)
        migrated.append(copy.deepcopy(ref))

    return {"version": 1, "format": FORMAT, "target": TARGET, "code": CODE, "participants": 27,
            "round_one": 22, "direct": 5, "round_one_ties": 11, "round_of_16": 16,
            "final_legs": 1, "other_knockout_legs": 2, "defending_champion_berth": False,
            "modules": config["modules"], "sources": sources, "places": places,
            "configuration": copy.deepcopy(config),
            "legacy_places": migrated, "previous_ids": copy.deepcopy(previous_ids or {}),
            "runtime_ready": False, "requires_new_career": True,
            "first_season": "entry_order_seed", "later_incomplete": "wait", "later_missing": "error"}


def resolve(pl, results=None, first_season=False, memberships=None):
    """Reference qualification for one season: no mutation, no implicit titleholder.

    results[source] = {status: complete|incomplete|missing|invalid, clubs: ranked ids}.
    First-season absent/incomplete results use declared league entry order; later ones
    must complete. A later enabled cup with missing/invalid results is an error, not off.
    """
    results = results or {}
    sources = copy.deepcopy(pl["sources"])
    for key, teams in (memberships or {}).items():
        key = str(key)
        if key not in sources or sources[key]["kind"] != "league" or not isinstance(teams, list) or not teams or any(type(t) is not int or t <= 0 for t in teams) or len(set(teams)) != len(teams):
            raise QualificationError("invalid current-season membership for source %s" % key)
        sources[key]["teams"] = list(teams)
        sources[key]["capacity"] = len(teams)
    known = {t for s in sources.values() if s["kind"] == "league" for t in s.get("teams", [])}
    if any(s["kind"] == "league" and "teams" not in s for s in sources.values()):
        raise QualificationError("qualification preview needs actual league memberships for every source")
    if len(known) < 27:
        raise QualificationError("current-season sources cannot supply 27 unique eligible clubs")
    pools = {}

    def pool(key):
        if key in pools:
            return pools[key]
        s = sources[key]
        r = results.get(key, {"status": "missing"})
        if not isinstance(r, dict) or r.get("status") not in ("complete", "incomplete", "missing", "invalid"):
            raise QualificationError("source %s has an invalid result status" % key)
        status = r["status"]
        if status == "complete":
            clubs = r.get("clubs")
            if not isinstance(clubs, list) or not clubs or any(type(t) is not int or t not in known for t in clubs) or len(set(clubs)) != len(clubs):
                raise QualificationError("source %s has invalid, duplicate or ineligible qualifying results" % key)
            if s["kind"] == "league" and set(clubs) != set(s["teams"]):
                raise QualificationError("league %s needs its complete ranked membership" % key)
            if s["kind"] == "cup":
                domestic = {t for v in sources.values() if v["kind"] == "league"
                            and v.get("country", "").lower() == s.get("country", "").lower()
                            for t in v.get("teams", [])}
                if any(t not in domestic for t in clubs):
                    raise QualificationError("cup source %s includes a club outside its domestic sources" % key)
            if s["kind"] == "regional":
                if len(clubs) < s["capacity"]:
                    raise QualificationError("regional source %s has no complete qualifying ranking" % key)
                domestic = [v for v in sources.values() if v["kind"] == "league" and v["region"] == s["region"]]
                if key == "module:leagues_cup":
                    domestic = [v for v in domestic if set(v["roles"]) & {"liga_mx", "mls"}]
                allowed = {t for v in domestic for t in v.get("teams", [])}
                if any(t not in allowed for t in clubs):
                    raise QualificationError("regional source %s includes an ineligible club" % key)
        elif first_season and status in ("missing", "incomplete"):
            clubs = s.get("teams", []) if s["kind"] == "league" else []
        elif status == "incomplete":
            raise QualificationPending("source %s has not completed its season; keep its berths pending" % key)
        else:
            raise QualificationError("source %s has %s results; its berths cannot be redistributed as disabled" % (key, status))
        pools[key] = clubs
        return clubs

    used, entries = set(), []
    # Reserve all five byes before assigning any Round One place.
    order = sorted(enumerate(pl["places"]), key=lambda x: (x[1]["stage"] != "round_of_16", x[0]))
    for index, slot in order:
        chosen, how, origin = None, "first_season_seed" if first_season else "completed_result", None
        for ref in slot["preferred"]:
            candidates = pool(ref["source"])[ref["rank"] - 1:]
            chosen = next((t for t in candidates if t not in used), None)
            if candidates and candidates[0] in used:
                how = "duplicate_qualification"
            if chosen is not None:
                origin = ref["source"]
                break
        if chosen is None:
            if how != "duplicate_qualification":
                how = "first_season_fallback" if first_season and slot["reason"] == "enabled_module" else slot["reason"]
            # Exhaust same-region ranks before crossing into other CONCACAF regions.
            for same_region in (True, False):
                keys = [k for k in slot["fallback"] if (sources[k]["region"] == PATH_REGION[slot["path"]]) == same_region]
                lists = [pool(k) for k in keys]
                for rank in range(max(map(len, lists), default=0)):
                    chosen = next((clubs[rank] for clubs in lists if rank < len(clubs) and clubs[rank] not in used), None)
                    if chosen is not None:
                        origin = next(k for k in keys if rank < len(pool(k)) and pool(k)[rank] == chosen)
                        break
                if chosen is not None:
                    break
        if chosen is None:
            raise QualificationError("CONCACAF Champions Cup cannot fill 27 unique clubs: no eligible replacement for %s/%s" % (slot["path"], slot["place"]))
        used.add(chosen)
        entries.append({"slot": index, "club": chosen, "stage": slot["stage"], "path": slot["path"], "how": how, "source": origin})
    if len(used) != 27 or sum(e["stage"] == "round_one" for e in entries) != 22 or sum(e["stage"] == "round_of_16" for e in entries) != 5:
        raise QualificationError("invalid CONCACAF plan: expected 27 unique clubs, 22 Round One and 5 direct")
    return sorted(entries, key=lambda e: e["slot"])
