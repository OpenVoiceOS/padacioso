"""``detach_skill`` removes only the intents the named skill owns. The owning
skill of ``a.b:c`` is exactly ``a.b`` (colon namespace separator, OVOS-MSG-1
§2.1.1), so a skill whose id is a substring of another skill's id must not
take the other skill's intents down with it."""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline


class TestDetachSkillPrefixMatch(unittest.TestCase):
    def setUp(self):
        self.p = PadaciosoPipeline(FakeBus(), {"any": 1})
        self.lang = self.p.lang

    def _register(self, name):
        self.p.register_intent(Message(
            "padatious:register_intent",
            {"name": name, "samples": ["hello " + name.split(":")[1]],
             "lang": self.lang}))

    def test_substring_skill_id_keeps_other_skills(self):
        for name in ("skill-a.me:one", "skill-b.me:bone", "me:mine"):
            self._register(name)
        self.p.handle_detach_skill(Message("detach_skill", {"skill_id": "me"}))
        self.assertEqual(sorted(self.p.registered_intents),
                         ["skill-a.me:one", "skill-b.me:bone"])
        names = set(self.p.containers[self.lang].intent_samples)
        self.assertIn("skill-a.me:one", names)
        self.assertIn("skill-b.me:bone", names)
        self.assertNotIn("me:mine", names)

    def test_unregistered_substring_skill_id_removes_nothing(self):
        for name in ("victim.skill:on", "otherskill:on"):
            self._register(name)
        self.p.handle_detach_skill(Message("detach_skill", {"skill_id": "skill"}))
        self.assertEqual(sorted(self.p.registered_intents),
                         ["otherskill:on", "victim.skill:on"])
        names = set(self.p.containers[self.lang].intent_samples)
        self.assertEqual(names & {"victim.skill:on", "otherskill:on"},
                         {"victim.skill:on", "otherskill:on"})
