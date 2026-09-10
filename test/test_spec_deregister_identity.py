"""A §8 message without a skill_id must not reach another skill's intent.

OVOS-INTENT-4 §3.2 makes ``(skill_id, intent_name, lang)`` the identity of an
intent. padacioso stores an intent under ``<skill_id>:<intent_name>``, so a
payload carrying only ``intent_name`` composes a bare name, which is exactly
what a legacy registration is stored under. Acting on it removes or suppresses
an intent the sender does not own.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline
from ovos_spec_tools import SpecMessage


def _pipeline():
    return PadaciosoPipeline(FakeBus(), {"fuzz": False})


class SpecDeregisterIdentityTest(unittest.TestCase):
    def setUp(self):
        self.pipe = _pipeline()
        # a legacy registration: the engine stores it under the bare name
        self.pipe.register_intent(Message("padatious:register_intent", {
            "name": "victim", "lang": "en-US",
            "samples": ["turn on the kitchen light"]}))
        self.assertIn("victim",
                      self.pipe.containers["en-US"].intent_samples)

    def _still_there(self):
        return "victim" in self.pipe.containers["en-US"].intent_samples

    def test_deregister_without_skill_id_leaves_the_victim(self):
        self.pipe.handle_deregister_intent(Message(
            SpecMessage.INTENT_DEREGISTER.value,
            {"intent_name": "victim", "lang": "en-US"}))
        self.assertTrue(self._still_there())

    def test_disable_without_skill_id_leaves_the_victim(self):
        self.pipe.handle_disable_intent(Message(
            SpecMessage.INTENT_DISABLE.value,
            {"intent_name": "victim", "lang": "en-US"}))
        self.assertTrue(self._still_there())

    def test_enable_without_skill_id_does_not_resolve_a_bare_name(self):
        self.pipe.handle_disable_intent(Message(
            SpecMessage.INTENT_DISABLE.value,
            {"skill_id": "other.skill", "intent_name": "victim",
             "lang": "en-US"}))
        self.pipe.handle_enable_intent(Message(
            SpecMessage.INTENT_ENABLE.value,
            {"intent_name": "victim", "lang": "en-US"}))
        self.assertTrue(self._still_there())

    def test_deregister_entity_without_skill_id_leaves_the_victim(self):
        self.pipe.register_entity(Message("padatious:register_entity", {
            "name": "victim_entity", "lang": "en-US", "samples": ["kitchen"]}))
        self.assertIn("victim_entity",
                      self.pipe.containers["en-US"].entity_samples)
        self.pipe.handle_deregister_entity(Message(
            SpecMessage.ENTITY_DEREGISTER.value,
            {"entity_name": "victim_entity", "lang": "en-US"}))
        self.assertIn("victim_entity",
                      self.pipe.containers["en-US"].entity_samples)

    def test_a_complete_payload_still_works(self):
        self.pipe.handle_register_template(Message(
            SpecMessage.INTENT_REGISTER_TEMPLATE.value,
            {"skill_id": "owner.skill", "intent_name": "own",
             "lang": "en-US", "samples": ["play some jazz"]}))
        self.assertIn("owner.skill:own",
                      self.pipe.containers["en-US"].intent_samples)
        self.pipe.handle_deregister_intent(Message(
            SpecMessage.INTENT_DEREGISTER.value,
            {"skill_id": "owner.skill", "intent_name": "own",
             "lang": "en-US"}))
        self.assertNotIn("owner.skill:own",
                         self.pipe.containers["en-US"].intent_samples)


if __name__ == "__main__":
    unittest.main()
