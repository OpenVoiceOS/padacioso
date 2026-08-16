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
