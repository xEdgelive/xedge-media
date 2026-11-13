#!/usr/bin/env python3
"""Checks for render_video.py's football scenes (the creative upgrade, 13 Nov 2026). Needs no network or voice.

    python3 tools/test_render_video.py

The frame test also needs Playwright with a browser (set XEDGE_CHROMIUM like the renderer); without one it's skipped.
"""
import copy
import math
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import render_video as rv  # noqa: E402

HOOK = {"type": "hook", "title": "Same match. Why [[two prices?]]", "say": "Same match. So why two prices?"}
END = {"type": "end", "title": "Compare prices as chances"}
PITCH = {"type": "pitch_story", "kicker": "ILLUSTRATION · ONE ATTACK", "title": "One chance. [[Two outcomes.]]",
         "pitch_view": "half", "players": [{"side": "home", "x": 0.3, "y": 0.4}, {"side": "away", "x": 0.6, "y": 0.55}],
         "ball_path": [[0.3, 0.4], [0.62, 0.7], [0.99, 0.48]], "focus": "ball",
         "say": "A pass{1} out wide, then a shot{2} into the corner."}
COMPARE = {"type": "match_compare", "kicker": "ONE OUTCOME · EXAMPLE", "title": "Same match. [[Two prices.]]",
           "outcome": "Home win", "offers": [{"label": "PRICE A", "decimal_odds": 2.50}, {"label": "PRICE B", "decimal_odds": 2.75}],
           "say": "One price{1} is 2.50, another{2} is 2.75. As chances{3}, that's 40 and 36.4%.{4} A 3.6 point gap."}
SHOTS = {"type": "probability_pitch", "kicker": "A ONE IN FIVE CHANCE", "title": "A chance [[isn't a goal]]",
         "probability": 0.2, "trials": 10, "say": "Give ten shots{1} a one in five chance each.{2} About two go in."}
STAT = {"type": "football_stat", "kicker": "SAMPLE SIZE", "title": "60% [[of what?]]", "numerator": 6, "denominator": 10,
        "of_what": "matches", "say": "Six{1} out of ten matches{2} is 60%. Ten is a small sample."}


def spec(*scenes, hook=None):
    return {"scenes": [copy.deepcopy(hook or HOOK), *copy.deepcopy(list(scenes)), copy.deepcopy(END)]}


def problems(*scenes, hook=None):
    return rv.check(spec(*scenes, hook=hook))[0]


def with_(scene, **changes):
    out = copy.deepcopy(scene)
    for k, v in changes.items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    return out


class Accepts(unittest.TestCase):
    def test_new_scenes_and_hook_visuals(self):
        for visual in (None, "pitch", "goal"):
            hook = with_(HOOK, visual=visual)
            self.assertEqual(problems(PITCH, COMPARE, SHOTS, STAT, hook=hook), [], visual)

    def test_options(self):
        self.assertEqual(problems(with_(PITCH, pitch_view="full", focus="goal", players=None,
                                        say="A pass{1}, then a shot{2}.")), [])
        self.assertEqual(problems(with_(PITCH, focus="none", players=[{"id": "a1", "side": "home", "x": 0, "y": 1}])), [])
        three = with_(COMPARE, offers=[{"label": "EARLY", "decimal_odds": 3.4}, {"label": "MIDWEEK", "decimal_odds": 3.6},
                                       {"label": "KICKOFF", "decimal_odds": 3.25}], say="Three prices{1}{2}{3}{4}{5}.")
        self.assertEqual(problems(three), [])
        real = with_(COMPARE, source_status="real", match_label="Team A v Team B", source="Test source", date="2026-11-08")
        self.assertEqual(problems(real), [])
        self.assertEqual(problems(with_(STAT, decimals=1, numerator=0)), [])
        real_stat = with_(STAT, source_status="real", source="Test source", date="2026-05-24", competition="Test league",
                          window="One season", definition="Home wins")
        self.assertEqual(problems(real_stat), [])
        self.assertEqual(problems(with_(SHOTS, probability=1 / 3, trials=3)), [])

    def test_old_scenes_unchanged(self):
        old = {"scenes": [HOOK, {"type": "number", "number": "4.8%", "title": "The margin", "say": "That's 4.8%."},
                          {"type": "compare", "bars": [{"label": "Yours", "value": "55%"}, {"label": "Needed", "value": "60%", "hi": True}],
                           "say": "You{1} need{2} more."}, END]}
        self.assertEqual(rv.check(old)[0], [])


class Refuses(unittest.TestCase):
    def bad(self, scene, expect, hook=None):
        found = problems(scene, hook=hook)
        self.assertTrue(any(expect in p for p in found), f"wanted {expect!r} in {found}")

    def test_unknown_keys(self):
        self.bad(with_(PITCH, camera="spin"), "'camera' isn't used")
        self.bad(with_(COMPARE, display="raw_implied_probability"), "'display' isn't used")
        self.bad(with_(SHOTS, event="shot"), "'event' isn't used")
        self.bad(with_(STAT, value=60), "'value' isn't used")
        self.bad(with_(PITCH, players=[{"side": "home", "x": 0.1, "y": 0.1, "name": "x"}]), "can only have side, x, y and id")
        self.bad(with_(COMPARE, offers=[{"label": "A", "decimal_odds": 2.5, "pct": "40%"}, {"label": "B", "decimal_odds": 2.75}]),
                 "needs a label and decimal_odds, and nothing else")
        self.bad(HOOK, "visual must be", hook=with_(HOOK, visual="stadium"))

    def test_numbers(self):
        for odds in (float("nan"), float("inf"), -2.5, 1.0, 100.5, 2.555, True, "2.50"):
            self.bad(with_(COMPARE, offers=[{"label": "A", "decimal_odds": odds}, {"label": "B", "decimal_odds": 2.75}]), "decimal_odds")
        self.bad(with_(COMPARE, offers=[{"label": "A", "decimal_odds": 2.5}, {"label": "B", "decimal_odds": 2.5}]), "different prices")
        self.bad(with_(COMPARE, offers=[{"label": "A", "decimal_odds": 2.5}, {"label": "a", "decimal_odds": 2.6}]), "labels must be different")
        self.bad(with_(COMPARE, offers=[{"label": "A", "decimal_odds": 2.5}]), "2 or 3 offers")
        for p, k, msg in ((0, 10, "probability"), (1, 10, "probability"), (float("nan"), 10, "probability"),
                          (0.25, 10, "whole number (0.25 × 10 = 2.5)"), (0.2, 21, "trials"), (0.5, 1, "trials"),
                          (0.2, 10.0, "trials"), (0.5, True, "trials")):
            self.bad(with_(SHOTS, probability=p, trials=k), msg)
        for num, den, msg in ((7, 6, "can't be more"), (1, 0, "denominator"), (1, 101, "denominator"), (-1, 10, "numerator"),
                              (1.5, 10, "numerator"), (True, 10, "numerator")):
            self.bad(with_(STAT, numerator=num, denominator=den), msg)
        self.bad(with_(STAT, decimals=2), "decimals must be 0 or 1")
        self.bad(with_(STAT, decimals=True), "decimals must be 0 or 1")

    def test_pitch_geometry(self):
        self.bad(with_(PITCH, ball_path=[[0.5, 0.5]]), "ball_path needs")
        self.bad(with_(PITCH, ball_path=[[0.1, 0.1]] * 17), "ball_path needs")
        self.bad(with_(PITCH, ball_path=[[0.1, 0.1], [1.2, 0.5]]), "ball_path needs")
        self.bad(with_(PITCH, ball_path=[[0.1, 0.1], [float("nan"), 0.5]]), "ball_path needs")
        self.bad(with_(PITCH, ball_path=[[0.1, 0.1], [0.1, 0.1], [0.9, 0.5]]), "under half a metre")
        self.bad(with_(PITCH, players=[{"side": "home", "x": 0.1, "y": 0.1}] * 23), "up to 22")
        self.bad(with_(PITCH, players=[{"side": "home", "x": -0.1, "y": 0.1}]), "numbers from 0 to 1")
        self.bad(with_(PITCH, players=[{"side": "keeper", "x": 0.1, "y": 0.1}]), "side must be")
        self.bad(with_(PITCH, players=[{"id": "a", "side": "home", "x": 0.1, "y": 0.1},
                                       {"id": "a", "side": "away", "x": 0.2, "y": 0.1}]), "ids must be different")
        self.bad(with_(PITCH, pitch_view="third"), "pitch_view must be")
        self.bad(with_(PITCH, focus="crowd"), "focus must be")
        self.bad(with_(PITCH, say="Too{1} many{2} beats{3} here."), "at most 2")

    def test_sources(self):
        self.bad(with_(COMPARE, source_status="real"), "need source")
        self.bad(with_(COMPARE, source_status="real", match_label="Team A v Team B", source="Test", date="2026-02-30"), "real date")
        self.bad(with_(COMPARE, source="Somewhere"), "only for real figures")
        self.bad(with_(COMPARE, source_status="rumour"), "source_status must be")
        self.bad(with_(STAT, source_status="real", source="Test", date="2026-05-24"), "need competition")
        self.bad(with_(STAT, definition="Home wins"), "only for real figures")

    def test_wording_and_lengths(self):
        self.bad(with_(COMPARE, offers=[{"label": "Bet365", "decimal_odds": 2.5}, {"label": "B", "decimal_odds": 2.75}]), "names a bookmaker")
        self.bad(with_(STAT, of_what="banker picks"), "banned wording")
        self.bad(with_(COMPARE, outcome="Home win and both teams"), "outcome is")
        self.bad(with_(STAT, title="x" * 51), "title is 51 characters")

    def test_switch(self):
        rv.FOOTBALL_SCENES = False
        try:
            self.bad(STAT, "switched off")
            self.bad(HOOK, "switched off", hook=with_(HOOK, visual="pitch"))
            self.assertEqual(rv.check({"scenes": [HOOK, {"type": "text", "title": "Plain", "say": "Plain."}, END]})[0], [])
        finally:
            rv.FOOTBALL_SCENES = True


class Maths(unittest.TestCase):
    def test_raw_implied(self):
        c = rv.compare_numbers(COMPARE)
        self.assertEqual([o["rawText"] for o in c["offers"]], ["40.0%", "36.4%"])
        self.assertEqual(c["gap"], {"hi": 0, "lo": 1, "text": "3.6"})
        c = rv.compare_numbers({"offers": [{"label": "A", "decimal_odds": 3.4}, {"label": "B", "decimal_odds": 3.6},
                                           {"label": "C", "decimal_odds": 3.25}]})
        self.assertEqual([o["rawText"] for o in c["offers"]], ["29.4%", "27.8%", "30.8%"])
        self.assertEqual(c["gap"]["text"], "3.0")  # 30.769 - 27.778, from the unrounded chances (not 30.8 - 27.8)

    def test_stats_round_half_up(self):
        self.assertEqual(rv.stat_numbers(STAT)["text"], "60%")
        self.assertEqual(rv.stat_numbers(with_(STAT, numerator=5, denominator=8))["text"], "63%")  # 62.5 -> 63
        self.assertEqual(rv.stat_numbers(with_(STAT, numerator=17, denominator=38, decimals=1))["text"], "44.7%")
        self.assertEqual(rv.stat_numbers(with_(STAT, numerator=1, denominator=3, decimals=1))["text"], "33.3%")

    def test_toy_shots(self):
        plan = rv.shot_plan(SHOTS)
        self.assertEqual(sum(s["goal"] for s in plan["list"]), 2)
        self.assertEqual([i for i, s in enumerate(plan["list"]) if s["goal"]], [2, 7])  # spread out, not last
        self.assertEqual((plan["pText"], plan["qText"]), ("20%", "80%"))
        gx, gy, gw, gh = rv.GOAL_BOX
        for s in plan["list"]:
            inside = gx < s["ix"] < gx + gw and gy < s["iy"] < gy + gh
            self.assertEqual(inside, s["goal"])
        for p, n in ((0.5, 2), (0.05, 20), (0.95, 20), (1 / 3, 3), (0.4, 5)):
            plan = rv.shot_plan(with_(SHOTS, probability=p, trials=n))
            self.assertEqual(sum(s["goal"] for s in plan["list"]), round(p * n))

    def test_pitch_mapping(self):
        g = rv.pitch_geometry(PITCH)
        self.assertEqual(g["pts"][0], [round(0.4 * 68, 3), round(0.7 * 52.5, 3)])  # half: goal at the top
        self.assertTrue(g["inGoal"])
        self.assertFalse(rv.pitch_geometry(with_(PITCH, ball_path=[[0.3, 0.4], [0.99, 0.43]]))["inGoal"])
        full = rv.pitch_geometry(with_(PITCH, pitch_view="full", ball_path=[[0, 0], [1, 1]]))
        self.assertAlmostEqual(full["total"], math.hypot(105, 68), places=2)


class Page(unittest.TestCase):
    def test_labels_and_no_remote_files(self):
        s = spec(PITCH, COMPARE, SHOTS, STAT, hook=with_(HOOK, visual="pitch"))
        html = "".join(rv.scene_html(i, sc) for i, sc in enumerate(s["scenes"]))
        for label in ("ILLUSTRATION", "EXAMPLE PRICES", "RAW IMPLIED", "TOY EXAMPLE", "NOT REAL DATA", "EXAMPLE · NOT REAL DATA"):
            self.assertIn(label, html)
        page = rv.page_html(s["scenes"], {"scenes": [], "caps": [], "total": 1})
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_old_scene_markup_unchanged(self):
        # An old hook (no visual) gets exactly the markup it always had.
        self.assertEqual(rv.scene_html(0, HOOK), '<section class="scene hook" id="s0"><h1 class="fit" data-min="64">'
                         '<span class="w">Same</span> <span class="w">match.</span> <span class="w">Why</span> '
                         '<span class="w hl">two</span> <span class="w hl">prices?</span></h1></section>')


@unittest.skipUnless(os.environ.get("XEDGE_CHROMIUM") or pathlib.Path.home().joinpath(".cache/ms-playwright").exists(),
                     "no browser for the frame test")
class Frames(unittest.TestCase):
    def test_same_frame_every_time(self):
        s = spec(PITCH, COMPARE, SHOTS, STAT, hook=with_(HOOK, visual="goal"))
        with tempfile.TemporaryDirectory() as work:
            tl = rv.build_timeline(s, pathlib.Path(work), True)
            times = [0.0, 0.5, 1.5] + [round(sc["t0"] + d, 2) for sc in tl["scenes"] for d in (0.3, 1.1, 2.4)]
            first = rv.stills(s, tl, times)
            again = rv.stills(s, tl, list(reversed(times)))[::-1]  # other frames in between, in another order
        self.assertEqual(first, again)


if __name__ == "__main__":
    unittest.main(verbosity=2)
