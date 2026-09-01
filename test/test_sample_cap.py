import unittest
from unittest.mock import patch

from ovos_spec_tools import expand

from padacioso import IntentContainer
from padacioso.__init__ import MAX_EXPANSIONS, _normalize


def _long_line():
    # each bracket has 20 alternatives -> 20*20*20 = 8000 expansions,
    # well past MAX_EXPANSIONS, forcing a per-line reservoir sample.
    a = "|".join(f"a{i}" for i in range(20))
    b = "|".join(f"b{i}" for i in range(20))
    c = "|".join(f"c{i}" for i in range(20))
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


if __name__ == "__main__":
    unittest.main()
