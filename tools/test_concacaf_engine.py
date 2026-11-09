"""Offline engine tests. CONCACAF_TEST_BASE enables table/build tests;
CONCACAF_TEST_DLL points at the newly compiled DLL. Never accesses an installed game.
"""
import contextlib
import copy
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import concacaf as Q
import leaguebuilder as B
import mkconcacaf as G
import mkleague as M

REPO = Path(__file__).resolve().parent.parent
BASE = os.environ.get("CONCACAF_TEST_BASE")
DLL = os.environ.get("CONCACAF_TEST_DLL")
LUA = REPO / "sider/experimental/fl26swiss.lua"


class ContractTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt" and shutil.which("gcc"), "Windows GCC scheduler harness")
    def test_native_calendar_conflicts(self):
        with tempfile.TemporaryDirectory(prefix="concacaf-calendar-") as root:
            exe = Path(root)/"calendar.exe"
            subprocess.run([shutil.which("gcc"),"-O2","-fno-builtin-logf","-o",str(exe),
                            str(REPO/"tools/native/test_concacaf_calendar.c"),"-lkernel32"],check=True,capture_output=True)
            run = subprocess.run([str(exe)],check=True,capture_output=True,text=True)
            self.assertIn("three days clear",run.stdout)

    def test_enabled_feeders_rejected(self):
        from test_concacaf import sources
        for flags in itertools.product((False,True), repeat=3):
            if not any(flags):
                continue
            p = Q.plan({"modules": dict(zip(Q.MODULES,flags))}, sources())
            with self.assertRaisesRegex(Q.QualificationError, "not implemented"):
                G.supported(p)

    @unittest.skipUnless(DLL, "set CONCACAF_TEST_DLL")
    def test_exports_and_outdated_runtime(self):
        exports = G.check_runtime(DLL, LUA)
        self.assertIn("fl26_swiss_install", exports)
        baseline = REPO / "out/concacaf-engine/fl26swiss-baseline.dll"
        if baseline.exists():
            with self.assertRaisesRegex(Q.QualificationError, "contract v1"):
                G.check_runtime(baseline, LUA)

    def test_complete_calendar(self):
        days = G.PRE_DAYS + G.KO_DAYS
        self.assertEqual(9, len(set(days)))
        self.assertEqual(sorted(days), list(days))
        self.assertTrue(all(b-a >= 7 for a,b in zip(days, days[1:])))
        self.assertLess(days[-1], 182)
        # 22 R1 matches + 16 R16 + 8 QF + 4 SF + 1 final = 51.
        self.assertEqual(51, 11*2 + 8*2 + 4*2 + 2*2 + 1)


@unittest.skipUnless(BASE, "set CONCACAF_TEST_BASE")
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="concacaf-engine-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.recipe = {"world": "_FL26TestConcacafEngine", "leagues": [], "concacaf": {}}
        self.plan = B.plan(self.recipe, BASE)

    def generate(self):
        cids, regs = B.free_comp_ids(BASE)
        self.ids = cids[0], regs[0], cids[1], regs[1]
        with contextlib.redirect_stdout(io.StringIO()):
            return G.generate(BASE, str(self.root), self.plan["concacaf"], *self.ids, log=lambda _:None)

    def test_database_structure_and_unrelated_rows(self):
        lines = self.generate()
        cid, ko, helper, pre = self.ids
        db = self.root / "common/etc/pesdb"
        raw = M.load(str(db), "CompetitionRegulation.bin")
        before = M.load(BASE, "CompetitionRegulation.bin")
        self.assertEqual(before, raw[:len(before)])
        rows = [raw[i:i+M.REG] for i in range(0,len(raw),M.REG)]
        mine = [r for r in rows if r[M.R_CID] == helper]
        self.assertEqual(12, len(mine))
        self.assertEqual({pre+1024*i for i in range(12)}, {int.from_bytes(r[2:4],"little") for r in mine})
        self.assertTrue(all((r[M.R_TEAMS]&63)==22 for r in mine))
        self.assertTrue(all((int.from_bytes(r[16:20],"little")>>9)&7 == 2 for r in mine))
        knockout = next(r for r in rows if int.from_bytes(r[2:4],"little")==ko)
        self.assertEqual(16, knockout[M.R_TEAMS]&63)
        flags = int.from_bytes(knockout[16:20],"little")
        self.assertEqual(1, (flags>>9)&7)  # two legs except final
        self.assertFalse(flags & ((1<<29)|(1<<28)))
        entries = M.load(str(db),"CompetitionEntry.bin")
        teams = [int.from_bytes(entries[i:i+4],"little") for i in range(0,len(entries),M.ENT) if entries[i+M.E_CID]==cid]
        self.assertEqual(27, len(set(teams)))
        self.assertEqual(3, len(lines))
        self.assertTrue(lines[-1].startswith("concacaf 1 data="))

    def test_native_contract_and_handover(self):
        lines = self.generate()
        data = list(map(int,lines[-1].split("data=")[1].split(",")))
        path = self.root / "contract.bin"
        path.write_bytes(struct.pack("<%dH"%len(data),*data))
        compiler = shutil.which("gcc")
        if not compiler:
            self.skipTest("gcc unavailable")
        exe = self.root / "test_concacaf.exe"
        subprocess.run([compiler,"-O2","-Wall","-Wextra","-o",str(exe),str(REPO/"tools/native/test_concacaf.c")],check=True,capture_output=True)
        run = subprocess.run([str(exe),str(path)],check=True,capture_output=True,text=True)
        self.assertIn("passed",run.stdout)

    @unittest.skipUnless(DLL, "set CONCACAF_TEST_DLL")
    def test_build_round_trip_and_stable_ids(self):
        # Read the staged runtime; Build itself writes only a temporary fake game.
        game = str(self.root / "game")
        def check(_): G.check_runtime(DLL,LUA)
        def build(recipe, prev=None):
            pl = B.plan(recipe,BASE,prev)
            with patch.object(B,"check_concacaf_runtime",side_effect=check):
                B.build(pl,BASE,game,replace=prev is not None,log=lambda _:None)
            path = Path(B.siderdir.find(game))/"livecpk"/recipe["world"]
            return json.loads((path/"leaguebuilder-plan.json").read_text(encoding="utf-8")), (path/"fl26world.txt").read_text(encoding="utf-8")
        first, world = build(self.recipe)
        primary, helper = "ccup:FL_CONCACAF", "concacaf:FL_CCC_R1"
        self.assertIn("concacaf 1 data=",world)
        self.assertTrue(first["concacaf"]["runtime_ready"])
        restored = B.recipe_from_plan(first,BASE)
        second, _ = build(restored,first)
        for key in (primary,helper): self.assertEqual(first["cup_ids"][key],second["cup_ids"][key])
        restored["leagues"] = [{"name":"Test Mexico", "country":"Mexico", "clubs":14, "cup":True}]
        third, _ = build(restored,second)
        for key in (primary,helper): self.assertEqual(first["cup_ids"][key],third["cup_ids"][key])

    @unittest.skipUnless(DLL, "set CONCACAF_TEST_DLL")
    def test_compatibility_guard_before_writes(self):
        pack = self.root/"pack/modules"
        pack.mkdir(parents=True)
        (pack/"fl26swiss.dll").write_bytes(b"old or invalid DLL")
        shutil.copy2(LUA,pack/"fl26swiss.lua")
        with patch.object(B,"pack_dir",return_value=str(pack.parent)), patch.object(B.flpaths,"use_game") as access:
            with self.assertRaisesRegex(B.BuildError,"runtime compatibility"):
                B.build(self.plan,BASE,str(self.root/"game"))
            access.assert_not_called()
        self.assertFalse((self.root/"game").exists())
        shutil.copy2(DLL,pack/"fl26swiss.dll")
        with patch.object(B,"pack_dir",return_value=str(pack.parent)):
            B.check_concacaf_runtime(self.plan)

    def test_activation_rejects_old_modules_before_ini_changes(self):
        world = self.root/"livecpk"/self.recipe["world"]
        world.mkdir(parents=True)
        (world/B.MARK).write_text("concacaf 1 data=1,200,201,243,33,40,1\n",encoding="utf-8")
        with patch.object(B.siderdir,"find",return_value=str(self.root)):
            with self.assertRaisesRegex(B.BuildError,"activation refused"):
                B.switch_on(self.recipe["world"],str(self.root))
        self.assertFalse((self.root/"sider.ini").exists())


if __name__ == "__main__":
    unittest.main()
