"""python tools/test_cwc32.py [pesdb folder]

Synthetic unit regressions; optional real-table plan/build/rebuild and disabled parity checks.
All generated worlds live in a temporary game folder, never the installed game.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import leaguebuilder as B
import mkcwc as C
import mksplit

M = C.M
QUIET = lambda _s: None


def row(rid, cid, group=255, clubs=4, kind=5):
    r = bytearray(M.REG)
    r[M.R_ID:M.R_ID + 2] = rid.to_bytes(2, 'little')
    r[M.R_CID], r[C.R_GROUP], r[M.R_TEAMS], r[M.R_TYPE] = cid, group, clubs, kind
    return r


def fixture():
    old = row(1, 1, kind=3)
    M.put_names(old, 0, 'Club World Cup')
    # Shipped CWC: single leg, extra time, penalties AND a third-place game.
    old[0x10:0x14] = (0x3ac00000).to_bytes(4, 'little')
    master = row(9, 5, clubs=32, kind=2)
    # Actual Libertadores flags: two round robins and leg subtype 1, policy 7.
    master[0x10:0x14] = (0x408422e8).to_bytes(4, 'little')
    replicas = []
    for g in range(8):
        replica = row(9 + 1024 * (g + 1), 5, g, clubs=32, kind=2)
        replica[0x10:0x14] = master[0x10:0x14]
        replicas.append(replica)
    return old + master + b''.join(replicas)


class CwcTests(unittest.TestCase):
    def test_shape_and_preservation(self):
        source = fixture()
        before = bytes(source)
        result = C.reshape(source, log=QUIET)
        self.assertEqual(bytes(source), before)
        rows = C.rows(result)
        ours = [r for r in rows if r[M.R_CID] == 1]
        self.assertEqual([C.rid(r) for r in ours], [1] + [1 + 1024 * k for k in range(1, 9)] + [200])
        self.assertEqual(ours[0][M.R_TEAMS] & 63, 32)
        self.assertEqual(ours[-1][M.R_TEAMS] & 63, 16)
        for r in ours[:-1]:
            self.assertEqual((int.from_bytes(r[0x10:0x14], 'little') >> 12) & 7, 1)
            for names in C.NAME_RUNS:
                self.assertEqual(r[names], source[:M.REG][names])
        for r in ours[1:-1]:
            self.assertEqual(int.from_bytes(r[6:8], 'little'), 1)
        self.assertEqual(b''.join(r for r in rows if r[M.R_CID] != 1), source[M.REG:])

    def test_collisions(self):
        for rid in (200, 1224, 1025, 8193):
            with self.subTest(rid=rid), self.assertRaises(ValueError):
                C.reshape(fixture() + row(rid, 50), log=QUIET)

    def test_63_match_structure(self):
        source = fixture()
        ours = [r for r in C.rows(C.reshape(source, log=QUIET)) if r[M.R_CID] == 1]
        group, knockout = ours[0], ours[-1]
        rules = int.from_bytes(knockout[0x10:0x14], 'little')
        self.assertFalse(rules & (1 << 28), 'no bronze fixture')
        self.assertEqual((rules >> 9) & 7, 0, 'single-leg subtype in every round')
        self.assertTrue(rules & (1 << 29))
        self.assertTrue(rules & (1 << 25), 'drawn final has extra time')
        self.assertTrue(rules & (1 << 27), 'drawn final can reach penalties')
        self.assertFalse(rules & (1 << 24))
        self.assertEqual(knockout[0x0c:0x10], source[0x0c:0x10], 'original CWC format/final retained')
        group_rules = int.from_bytes(group[0x10:0x14], 'little')
        groups, clubs = group_rules & 31, group[M.R_TEAMS] & 63
        rounds = (group_rules >> 12) & 7
        field = knockout[M.R_TEAMS] & 63
        self.assertEqual((groups, clubs // groups, rounds, field), (8, 4, 1, 16))
        # A round robin supplies every pair once; elimination removes one club per match.
        self.assertEqual(groups * (clubs // groups) * (clubs // groups - 1) // 2 * rounds, 48)
        self.assertEqual(field - 1, 15)
        self.assertEqual(48 + field - 1, 63)

    def test_group_metadata_and_scoping(self):
        source = fixture()
        # A different competition with a bronze game must keep it, even at another KO id.
        other = row(50, 50, clubs=16, kind=3)
        other[0x10:0x14] = (0x3ac00000).to_bytes(4, 'little')
        source += other
        generated = C.rows(C.reshape(source, ko=201, log=QUIET))
        self.assertEqual(generated[-1], other)
        groups = [r for r in generated if r[M.R_CID] == 1 and C.rid(r) != 201]
        for r in groups:
            rules = int.from_bytes(r[0x10:0x14], 'little')
            self.assertEqual((rules >> 12) & 7, 1)
            self.assertEqual((rules >> 9) & 7, 0, 'Rules text must select single meeting')
            self.assertEqual((rules >> 5) & 15, 7, 'do not repurpose calendar/ranking policy')
            self.assertFalse(rules & (1 << 24), 'two-leg away-goals flag was already off')
            self.assertEqual(rules & ~((7 << 12) | (7 << 9)), 0x408422e8 & ~((7 << 12) | (7 << 9)))
        knockout = next(r for r in generated if C.rid(r) == 201)
        self.assertFalse(int.from_bytes(knockout[0x10:0x14], 'little') & (1 << 28))
        self.assertEqual(b''.join(r for r in generated if r[M.R_CID] != 1), source[M.REG:])

    def test_bad_input(self):
        for source in (fixture()[:-1], fixture()[M.REG:], C.reshape(fixture(), log=QUIET)):
            with self.assertRaises(ValueError):
                C.reshape(source, log=QUIET)
        for ko in (175, 1024):
            with self.assertRaises(ValueError):
                C.reshape(fixture(), ko, log=QUIET)
        source = fixture()
        source[-M.REG + C.R_GROUP] = 0
        with self.assertRaises(ValueError):
            C.reshape(source, log=QUIET)
        source = fixture()
        source[M.R_TEAMS] = 16
        with self.assertRaises(ValueError):
            C.reshape(source, log=QUIET)

    def test_flag(self):
        self.assertFalse(B.cwc32_enabled({}))
        self.assertEqual(B.cwc_reserved({'cwc32': True}), {200})
        self.assertEqual(B.cwc_reserved({'cwc32': False}), set())
        self.assertTrue(B.has_edits({'cwc32': True}))
        for v in ('true', 1, None, [], {}):
            with self.assertRaises(B.BuildError):
                B.cwc32_enabled({'cwc32': v})

    def test_runtime_contract(self):
        native = Path(__file__).with_name('native').joinpath('fl26swiss.c').read_text(encoding='utf-8')
        import re
        self.assertEqual(int(re.search(r'#define CWC_KO\s+(\d+)', native)[1]), C.CWC_KO)

    def test_api_cli_and_dry(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t, 'base')
            M.write_tables(str(base), bytearray(M.COMP), fixture(), bytearray(M.ENT))
            db = base / 'common/etc/pesdb'
            dest = Path(t, 'out')
            C.build(str(db), str(dest), dry=True, log=QUIET)
            self.assertFalse(dest.exists())
            self.assertEqual(C.main(['--base', str(db), '--dry']), 0)
            C.main(['--base', str(db), '--out', str(dest)])
            outdb = dest / 'common/etc/pesdb'
            self.assertEqual(M.load(str(outdb), 'CompetitionRegulation.bin'), C.reshape(fixture(), log=QUIET))
            for name in ('Competition.bin', 'CompetitionEntry.bin'):
                self.assertEqual(M.load(str(db), name), M.load(str(outdb), name))

    def test_allocators_and_split(self):
        with tempfile.TemporaryDirectory() as t:
            regs = fixture() + b''.join(row(i, 50, kind=4, clubs=12) for i in range(191, 200))
            M.write_tables(t, bytearray(M.COMP), regs, bytearray())
            db = os.path.join(t, 'common/etc/pesdb')
            self.assertNotIn(200, B.free_comp_ids(db, reserved={200})[1])
            # Current slot maps also exclude 200. Exercise the explicit reservation
            # independently so a future slot map cannot accidentally release it.
            with patch.dict(B.fl26world.DEFAULT_SLOT, {}, clear=True), patch.object(B.fl26world, 'NO_SLOT_IDS', set()):
                self.assertIn(200, B.free_comp_ids(db)[1])
                self.assertNotIn(200, B.free_comp_ids(db, reserved={200})[1])
            pl = {'cwc32': True, 'prev_cup_ids': {'cup:test': {'cid': 130, 'reg': 200}}}
            self.assertNotIn(200, B.pinned_ids(pl, db, 'cup:test')[1])
            with patch.object(sys, 'argv', ['mksplit', '--base', db, '--out', t,
                                           '--split', '191:12x2:6x1:6x1', '--reserve', '200']):
                self.assertEqual(mksplit.main(), 0)
            ids = {C.rid(r) for r in C.rows(M.load(db, 'CompetitionRegulation.bin'))}
            self.assertNotIn(200, ids)
            self.assertTrue({201, 202, 203} <= ids)


def integration(base):
    """Actual builder and table IO, with both switches and a split/national cup world."""
    recipe = {'world': '_FL26TestCwc32', 'leagues': [
        {'name': 'CWC Albania', 'country': 'Albania', 'clubs': 12, 'legs': 2,
         'split': {'legs': 2, 'groups': [6, 6], 'group_legs': 1}, 'cup': True}],
        'make_kits': False, 'pack_faces': False}
    with tempfile.TemporaryDirectory(prefix='cwc32-') as game:
        sider = Path(game, 'SiderAddons')
        for d in ('livecpk', 'modules', 'content'):
            (sider / d).mkdir(parents=True, exist_ok=True)
        (sider / 'sider.ini').write_text('[sider]\n')
        for enabled in (True, False):
            r = dict(recipe, cwc32=enabled)
            pl = B.plan(r, base)
            assert pl['cwc32'] is enabled
            assert B.recipe_from_plan(pl, base)['cwc32'] is enabled
            assert ('knockout regulation 200' in B.describe(pl)) is enabled
            out = B.build(pl, base, game, replace=not enabled, log=QUIET)
            db = Path(out, 'common/etc/pesdb')
            before = (db / 'CompetitionRegulation.bin').read_bytes()
            regs = M.load(str(db), 'CompetitionRegulation.bin')
            ours = [x for x in C.rows(regs) if x[M.R_CID] == 1]
            assert len(ours) == (10 if enabled else 1)
            if enabled:
                ko = next(x for x in ours if C.rid(x) == 200)
                rules = int.from_bytes(ko[0x10:0x14], 'little')
                assert not rules & (1 << 28) and rules & (1 << 29) and not (rules >> 9) & 7
                assert all(not (int.from_bytes(x[0x10:0x14], 'little') >> 9) & 7
                           for x in ours if C.rid(x) != 200)
            previous = json.loads(Path(out, 'leaguebuilder-plan.json').read_text(encoding='utf-8'))
            back = B.recipe_from_plan(previous, base)
            B.build(B.plan(back, base, previous), base, game, replace=True, log=QUIET)
            assert (db / 'CompetitionRegulation.bin').read_bytes() == before
            print('ok full build / round trip / rebuild: cwc32=%s' % enabled)
        # Omitted and explicitly false produce identical plans apart from stored settings.
        absent, off = B.plan(recipe, base), B.plan(dict(recipe, cwc32=False), base)
        off['settings'].pop('cwc32')
        assert absent == off
        B.build(absent, base, game, replace=True, log=QUIET)
        assert (db / 'CompetitionRegulation.bin').read_bytes() == before
        for previous in ({'cup_ids': {'cup:old': {'reg': 200}}}, {'leagues': [{'rid': 200}]}):
            try:
                B.plan(dict(recipe, cwc32=True), base, previous)
            except B.BuildError as e:
                assert '200' in str(e)
            else:
                raise AssertionError('previous regulation 200 owner silently displaced')
        print('ok disabled parity and previous-owner collision rejection')
        only = {'world': '_FL26TestCwcOnly', 'leagues': [], 'cwc32': True, 'uecl': False}
        recipe_path = Path(game, 'only.json')
        recipe_path.write_text(json.dumps(only), encoding='utf-8')
        out = B.build(B.plan(B.load_recipe(str(recipe_path)), base), base, game, log=QUIET)
        regs = M.load(os.path.join(out, 'common/etc/pesdb'), 'CompetitionRegulation.bin')
        assert sum(r[M.R_CID] == 1 for r in C.rows(regs)) == 10
        print('ok CWC-only recipe and Conference League disabled')


if __name__ == '__main__':
    base = sys.argv.pop(1) if len(sys.argv) > 1 else None
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        sys.exit(1)
    if base:
        integration(base)
