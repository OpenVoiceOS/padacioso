import unittest
from unittest.mock import patch

from ovos_spec_tools import expand

from padacioso import IntentContainer
from padacioso.__init__ import MAX_EXPANSIONS, _normalize


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


if __name__ == "__main__":
    unittest.main()
