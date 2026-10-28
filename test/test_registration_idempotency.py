"""Wire registration is replace-on-reregister (OVOS-INTENT-4 §8.1) on BOTH
contracts, in either arrival order — the dual-emit from ovos-workshop must
never trip the engine's strict re-registration guard (live-boot failure:
'Attempted to re-register existing entity')."""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline


class TestRegistrationIdempotency(unittest.TestCase):
    def setUp(self):
        self.p = PadaciosoPipeline(FakeBus(), {"any": 1})
        self.lang = self.p.lang

    def _legacy_entity(self, samples):
        self.p.register_entity(Message(
            "padatious:register_entity",
            {"name": "skill.test:location", "samples": samples,
             "lang": self.lang}))

    def _spec_entity(self, samples):
        self.p.handle_register_entity(Message(
            "ovos.entity.register",
            {"skill_id": "skill.test", "entity_name": "location",
             "samples": samples, "lang": self.lang}))

    def test_legacy_twice_replaces(self):
        self._legacy_entity(["porto"])
        self._legacy_entity(["lisbon"])  # must not raise
        c = self.p.containers[self.lang]
        self.assertEqual(
            sum(1 for n in c.entity_samples if "location" in n), 1)

    def test_spec_then_legacy_replaces(self):
        self._spec_entity(["porto"])
        self._legacy_entity(["lisbon"])  # the live-boot crash path
        c = self.p.containers[self.lang]
        self.assertEqual(
            sum(1 for n in c.entity_samples if "location" in n), 1)

    def test_legacy_then_spec_replaces(self):
        self._legacy_entity(["porto"])
        self._spec_entity(["lisbon"])
        c = self.p.containers[self.lang]
        self.assertEqual(
            sum(1 for n in c.entity_samples if "location" in n), 1)

    def test_legacy_intent_twice_replaces(self):
        msg = Message("padatious:register_intent",
                      {"name": "skill.test:go.intent",
                       "samples": ["go to {place}"], "lang": self.lang})
        self.p.register_intent(msg)
        self.p.register_intent(msg)  # skill reload; must not raise
        c = self.p.containers[self.lang]
        self.assertEqual(
            sum(1 for n in c.intent_samples if "go" in n), 1)


if __name__ == "__main__":
    unittest.main()


class TestEngineReplaceSemantics(unittest.TestCase):
    """Engine-level add is last-write-wins: concurrent wire registrations
    (thread-pooled handlers, dual contracts) cannot be serialized by the
    callers, so a strict raise crashes skill loading under races."""

    def test_add_intent_twice_replaces(self):
        from padacioso import IntentContainer
        c = IntentContainer()
        c.add_intent("greet", ["hello {name}"])
        c.add_intent("greet", ["hi {name}"])  # must not raise
        self.assertEqual(len([n for n in c.intent_samples if n == "greet"]), 1)

    def test_add_entity_twice_replaces(self):
        from padacioso import IntentContainer
        c = IntentContainer()
        c.add_entity("city", ["porto"])
        c.add_entity("city", ["lisbon"])  # must not raise
        self.assertEqual(len([n for n in c.entity_samples if n == "city"]), 1)

    def test_concurrent_registration_never_raises(self):
        from concurrent.futures import ThreadPoolExecutor
        from padacioso import IntentContainer
        c = IntentContainer()
        def reg(i):
            c.add_intent("race", [f"sample {i} {{x}}"])
            c.add_entity("slot", [f"value{i}"])
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(reg, range(50)))
        self.assertIn("race", c.intent_samples)
        self.assertIn("slot", c.entity_samples)


class TestBoundedExpansion(unittest.TestCase):
    """Expanded samples are resident for the process lifetime (regex string
    + two matchers each): an unbounded bracket product in one template must
    not materialize past the cap."""

    def test_intent_bracket_product_bounded(self):
        from padacioso import IntentContainer, MAX_EXPANSIONS
        c = IntentContainer()
        # 20^4 = 160k combinations from one line
        opts = "(" + "|".join(f"w{i}" for i in range(15)) + ")"
        c.add_intent("boom", [f"{opts} {opts} {opts}"])
        self.assertLessEqual(len(c.intent_samples["boom"]), MAX_EXPANSIONS)
        self.assertGreater(len(c.intent_samples["boom"]), 0)

    def test_small_intents_unbounded_behavior_unchanged(self):
        from padacioso import IntentContainer
        c = IntentContainer()
        c.add_intent("greet", ["(hi|hello) {name}"])
        self.assertEqual(len(c.intent_samples["greet"]), 2)

    def test_entity_expansion_bounded(self):
        from padacioso import IntentContainer, MAX_EXPANSIONS
        c = IntentContainer()
        opts = "(" + "|".join(f"v{i}" for i in range(15)) + ")"
        c.add_entity("big", [f"{opts} {opts} {opts}"])
        self.assertLessEqual(len(c.entity_samples["big"]), MAX_EXPANSIONS)
