import unittest
from unittest.mock import patch

from ovos_spec_tools import expand

from padacioso import IntentContainer
from padacioso.__init__ import MAX_EXPANSIONS, _fair_rations, _normalize


def _long_line():
    # each bracket has 40 alternatives -> 40*40*40 = 64000 expansions,
    # well past a two-line share of MAX_EXPANSIONS, forcing a per-line
    # reservoir sample.
    a = "|".join(f"a{i}" for i in range(40))
    b = "|".join(f"b{i}" for i in range(40))
    c = "|".join(f"c{i}" for i in range(40))
    return f"({a}) ({b}) ({c})"


class TestSampleCap(unittest.TestCase):
    def test_tail_expansion_survives_uniform_sampling(self):
        long_line = _long_line()
        short_line = "hello there"
        container = IntentContainer()
        container.add_intent("weather", [long_line, short_line])
        samples = container.intent_samples["weather"]

        expansions = list(expand(long_line))
        self.assertGreater(len(expansions), MAX_EXPANSIONS)

        head = _normalize(expansions[0])
        tail = _normalize(expansions[-1])
        self.assertIn(head, samples)
        self.assertIn(tail, samples,
                       "uniform sampling should keep coverage from the tail "
                       "of a truncated line, not just its first N expansions")

    def test_warning_names_intent_and_line(self):
        long_line = _long_line()
        container = IntentContainer()
        with patch("padacioso.__init__.LOG.warning") as mock_warning:
            container.add_intent("weather", [long_line, "hello there"])
        mock_warning.assert_called_once()
        message = mock_warning.call_args[0][0]
        self.assertIn("weather", message)
        self.assertIn("line 0", message)
        self.assertIn(str(MAX_EXPANSIONS), message)

    def test_deterministic_sampling(self):
        long_line = _long_line()
        c1 = IntentContainer()
        c1.add_intent("weather", [long_line, "hello there"])
        c2 = IntentContainer()
        c2.add_intent("weather", [long_line, "hello there"])
        self.assertEqual(sorted(c1.intent_samples["weather"]),
                          sorted(c2.intent_samples["weather"]))

    def test_short_line_untouched(self):
        container = IntentContainer()
        container.add_intent("hello", ["(hello|hi|hey) world"])
        self.assertEqual(sorted(container.intent_samples["hello"]),
                          sorted(["hello world", "hi world", "hey world"]))


class TestSilentCoverageLoss(unittest.TestCase):
    """Regression test for the silent-coverage bug: a phrasing dropped by
    the expansion cap can NEVER match, because the compiled samples kept
    here are the only regexes calc_intent ever tests a query against.

    Uses a single template line that expands past the OLD default
    (MAX_EXPANSIONS = 2000) but stays comfortably under the NEW default
    (50000), so a container built with the old, too-tight cap drops the
    phrasing while the new default keeps it.
    """

    @staticmethod
    def _template_line():
        # 15 * 15 * 15 = 3375 expansions from one line: past the old
        # default of 2000, well under the new default of 50000.
        a = "|".join(f"alpha{i}" for i in range(15))
        b = "|".join(f"bravo{i}" for i in range(15))
        c = "|".join(f"charlie{i}" for i in range(15))
        return f"turn on the ({a}) ({b}) ({c}) light"

    def test_phrasing_beyond_old_cap_matches_at_new_default(self):
        line = self._template_line()
        expansions = list(expand(line))
        self.assertGreater(len(expansions), 2000)
        self.assertLess(len(expansions), 50000)

        # fails against the OLD default: reservoir sampling is uniform, not
        # deterministic-by-position, so find a phrasing this specific
        # container's cap actually dropped rather than assuming the tail is
        # the one dropped.
        old_container = IntentContainer(max_expansions=2000)
        old_container.add_intent("lights", [line])
        kept = set(old_container.intent_samples["lights"])
        missed_phrasing = next(
            _normalize(e) for e in expansions if _normalize(e) not in kept)

        # the phrasing was never compiled, so calc_intent cannot match it
        # no matter how it is phrased
        result = old_container.calc_intent(missed_phrasing)
        self.assertIsNone(
            result["name"],
            "at the old default (2000) this phrasing was silently dropped "
            "and can never match, reproducing the coverage bug")

        # passes against the library default (50000, still configurable
        # via IntentContainer(max_expansions=...) for a deployment that
        # needs a different bound)
        new_container = IntentContainer()
        new_container.add_intent("lights", [line])
        result = new_container.calc_intent(missed_phrasing)
        self.assertEqual(result["name"], "lights")


class TestEntityUniformSampling(unittest.TestCase):
    """Entity expansion used to hard-truncate (keep only the first N
    expansions of concatenated lines), so any value expanding past the cap
    could never validate a match against that entity — unlike add_intent's
    already-uniform per-line sampling. Verifies add_entity now spreads and
    samples the same way.
    """

    @staticmethod
    def _entity_line():
        # 20 * 20 * 20 = 8000 values from one line: past the old default
        # of 2000, well under the new default of 50000.
        a = "|".join(f"a{i}" for i in range(20))
        b = "|".join(f"b{i}" for i in range(20))
        c = "|".join(f"c{i}" for i in range(20))
        return f"({a}) ({b}) ({c})"

    def test_full_range_survives_at_old_cap(self):
        line = self._entity_line()
        expansions = list(expand(line))
        self.assertGreater(len(expansions), 2000)

        # the old hard truncation kept only the first 2000 values in
        # expansion order, which never reached the later "c" alternatives
        # (measured: only c0-c4 out of c0-c19 survived). Uniform sampling
        # keeps coverage from across the whole range instead.
        container = IntentContainer(max_expansions=2000)
        container.add_entity("colors", [line])
        c_suffixes = {v.split()[-1] for v in container.entity_samples["colors"]}
        self.assertGreater(
            len(c_suffixes), 15,
            "uniform sampling should keep values spanning the full 'c' "
            "range, not just the first few reached by hard truncation")

    def test_no_values_dropped_at_new_default(self):
        line = self._entity_line()
        expansions = set(expand(line))
        container = IntentContainer()
        container.add_entity("colors", [line])
        self.assertEqual(container.entity_samples["colors"], expansions)


class TestTheBudgetIsAPool(unittest.TestCase):
    """The cap is spent as ONE pool across an intent's lines.

    It was ``max_expansions // len(lines)``, an equal ration whatever the
    file used in total. Measured on ovos-skill-weather en-US at dev
    e59b275e: 58 lines expanding to 5,593 in total, a ninth of the default
    budget, and yet a ration of 50000 // 58 = 862 cost one 2,688-expansion
    line 1,826 phrasings. Over that line's 1,344 slot-free phrasings only
    525 matched. A phrasing dropped here can never match.
    """

    @staticmethod
    def _fat_line():
        # 4 * 2 * 7 * 12 * 2 * 2 = 2688, the shape of the weather line
        q = "|".join(f"q{i}" for i in range(4))
        w = "|".join(f"w{i}" for i in range(2))
        d = "|".join(f"d{i}" for i in range(7))
        h = "|".join(f"h{i}" for i in range(12))
        m = "|".join(f"m{i}" for i in range(2))
        n = "|".join(f"n{i}" for i in range(2))
        return f"({q}) ({w}) ({d}) ({h}) ({m}) ({n})"

    def test_a_file_under_the_budget_keeps_every_phrasing(self):
        """The defect. 2688 in a file of 2688 + 57 short lines, budget 50000."""
        fat = self._fat_line()
        lines = [fat] + [f"short phrase {i}" for i in range(57)]
        grand_total = sum(len(list(expand(line))) for line in lines)
        self.assertLess(grand_total, MAX_EXPANSIONS,
                        "the premise moved: this file must fit in the budget")

        container = IntentContainer()
        container.add_intent("weather", lines)
        kept = set(container.intent_samples["weather"])

        missing = [_normalize(e) for e in expand(fat)
                   if _normalize(e) not in kept]
        self.assertEqual([], missing,
                         f"{len(missing)} phrasings dropped from a file at "
                         f"{grand_total} of a {MAX_EXPANSIONS} budget")

    def test_a_dropped_phrasing_can_never_match(self):
        """Why it matters: the kept samples are the only regexes tested."""
        fat = self._fat_line()
        lines = [fat] + [f"short phrase {i}" for i in range(57)]
        container = IntentContainer()
        container.add_intent("weather", lines)

        phrasings = [_normalize(e) for e in expand(fat)]
        matched = sum(1 for p in phrasings
                      if container.calc_intent(p)["name"] == "weather")
        self.assertEqual(len(phrasings), matched,
                         "a phrasing of a file well under the budget did not "
                         "match its own intent")

    def test_no_warning_when_the_total_fits(self):
        """The message said 'exceeds max_expansions=50000' about a line of
        2688, which reads as a file-size overflow and sent T-5120 looking for
        one. A file inside the budget must say nothing at all."""
        lines = [self._fat_line()] + [f"short phrase {i}" for i in range(57)]
        container = IntentContainer()
        with patch("padacioso.__init__.LOG.warning") as mock_warning:
            container.add_intent("weather", lines)
        self.assertEqual([], mock_warning.call_args_list)

    def test_adding_a_line_does_not_shrink_another_line(self):
        """The ration was a function of the neighbours, so the documented
        workaround -- split the fat line -- got tighter as a locale grew and
        could push a previously safe line over."""
        fat = self._fat_line()
        alone = _fair_rations([len(list(expand(fat)))], MAX_EXPANSIONS)[0]
        for extra in (10, 57, 200):
            totals = [len(list(expand(fat)))] + [4] * extra
            self.assertEqual(
                alone, _fair_rations(totals, MAX_EXPANSIONS)[0],
                f"{extra} extra lines lowered the fat line's ration")

    def test_a_real_overflow_is_still_bounded(self):
        """Pooling must not remove the bound. The budget is why it exists."""
        rations = _fair_rations([5000, 5000, 3], 1000)
        self.assertEqual(1000, sum(rations))
        self.assertEqual(3, rations[2], "the line that fits was not served whole")
        self.assertEqual([498, 499], sorted(rations[:2])[:2])

    def test_the_lines_that_fit_are_served_first(self):
        """Max-min: a line never loses anything to a line that already fits."""
        rations = _fair_rations([1, 1, 1, 10000], 100)
        self.assertEqual([1, 1, 1, 97], rations)

    def test_more_lines_than_budget_keeps_a_floor_of_one(self):
        """Every template contributes a sample, as before. This is the only
        case where the rations may add up to more than the budget."""
        rations = _fair_rations([9] * 12, 5)
        self.assertEqual([1] * 12, rations)

    def test_the_warning_names_the_ration_it_applied(self):
        """It said 'only 862 per overflowing line are kept' for a ration
        nothing in the file asked for. It must report what it really did."""
        fat = _long_line()  # 64000, a genuine overflow of the 50000 budget
        container = IntentContainer()
        with patch("padacioso.__init__.LOG.warning") as mock_warning:
            container.add_intent("weather", [fat, "hello there"])
        mock_warning.assert_called_once()
        message = mock_warning.call_args[0][0]
        self.assertIn("expands to 64001 samples", message)
        self.assertIn("49999 kept", message)
        self.assertNotIn("per overflowing line", message)


class TestTheEntityPathPoolsToo(unittest.TestCase):
    """The same accounting was written twice. A fix to one would leave the
    other, and an entity value that is never retained can never validate a
    match against that entity."""

    @staticmethod
    def _fat_line():
        a = "|".join(f"a{i}" for i in range(14))
        b = "|".join(f"b{i}" for i in range(14))
        c = "|".join(f"c{i}" for i in range(14))
        return f"({a}) ({b}) ({c})"   # 2744

    def test_an_entity_under_the_budget_keeps_every_value(self):
        fat = self._fat_line()
        lines = [fat] + [f"value{i}" for i in range(57)]
        grand_total = sum(len(list(expand(line))) for line in lines)
        self.assertLess(grand_total, MAX_EXPANSIONS)

        container = IntentContainer()
        container.add_entity("colors", lines)
        kept = container.entity_samples["colors"]

        missing = [e for e in expand(fat) if e not in kept]
        self.assertEqual([], missing,
                         f"{len(missing)} values dropped from an entity at "
                         f"{grand_total} of a {MAX_EXPANSIONS} budget")

    def test_no_warning_when_the_entity_total_fits(self):
        lines = [self._fat_line()] + [f"value{i}" for i in range(57)]
        container = IntentContainer()
        with patch("padacioso.__init__.LOG.warning") as mock_warning:
            container.add_entity("colors", lines)
        self.assertEqual([], mock_warning.call_args_list)


if __name__ == "__main__":
    unittest.main()
