"""T-7201: the entity value set a slot resolves to.

A template's slot name is bare (``{mediakind}``); the pipeline plugin registers
a skill's ``.entity`` list under ``<skill_id>:<entity_name>``, because two
skills may each declare a ``mediakind`` and one must not answer for the other.
The matcher looked the slot up bare, so no registered list was ever found and
none was ever enforced.
"""
import unittest

from ovos_spec_tools.expansion import MalformedTemplate

from padacioso import IntentContainer

ALERTS = "skill-alerts.openvoiceos"
MUSIC = "skill-music.openvoiceos"


class TestEntityKeyResolution(unittest.TestCase):
    def test_a_namespaced_list_gates_a_bare_slot(self):
        c = IntentContainer()
        c.add_intent(f"{ALERTS}:change_media", ["change my alarm to {mediakind}"])
        c.add_entity(f"{ALERTS}:mediakind", ["music", "radio"])
        member = c.calc_intent("change my alarm to music")["conf"]
        other = c.calc_intent("change my alarm to zzzqqq")["conf"]
        self.assertGreater(member, other,
                           f"member={member} non-member={other}")

    def test_a_bare_list_still_gates_a_bare_slot(self):
        """The fallback is not legacy tolerance: a container used without the
        pipeline registers entities under the plain name."""
        c = IntentContainer()
        c.add_intent(f"{ALERTS}:change_media", ["change my alarm to {mediakind}"])
        c.add_entity("mediakind", ["music", "radio"])
        self.assertGreater(c.calc_intent("change my alarm to music")["conf"],
                           c.calc_intent("change my alarm to zzzqqq")["conf"])

    def test_one_skills_list_never_answers_for_another(self):
        """The reason the namespace exists, asserted in both directions."""
        c = IntentContainer()
        c.add_intent(f"{ALERTS}:change_media", ["change my alarm to {mediakind}"])
        c.add_intent(f"{MUSIC}:play_media", ["play some {mediakind}"])
        c.add_entity(f"{ALERTS}:mediakind", ["radio"])
        c.add_entity(f"{MUSIC}:mediakind", ["jazz"])
        self.assertGreater(c.calc_intent("change my alarm to radio")["conf"],
                           c.calc_intent("change my alarm to jazz")["conf"],
                           "alerts must not accept music's value")
        self.assertGreater(c.calc_intent("play some jazz")["conf"],
                           c.calc_intent("play some radio")["conf"],
                           "music must not accept alerts' value")

    def test_a_slot_with_no_list_keeps_the_lighter_penalty(self):
        """Unregistered and registered-but-not-a-member stay distinct: the
        first is a skill that declared no list, the second is a wrong value."""
        unreg = IntentContainer()
        unreg.add_intent(f"{ALERTS}:change_media", ["change my alarm to {mediakind}"])
        no_list = unreg.calc_intent("change my alarm to zzzqqq")["conf"]

        reg = IntentContainer()
        reg.add_intent(f"{ALERTS}:change_media", ["change my alarm to {mediakind}"])
        reg.add_entity(f"{ALERTS}:mediakind", ["music"])
        wrong_value = reg.calc_intent("change my alarm to zzzqqq")["conf"]

        self.assertGreater(no_list, wrong_value,
                           "a declared list that the value fails must cost more "
                           f"than no list at all; no_list={no_list} "
                           f"wrong_value={wrong_value}")

    def test_the_resolver_prefers_the_owning_skill(self):
        c = IntentContainer()
        c.add_entity(f"{ALERTS}:mediakind", ["radio"])
        c.add_entity("mediakind", ["anything"])
        self.assertEqual(c._entity_key(f"{ALERTS}:change_media", "mediakind"),
                         f"{ALERTS}:mediakind")
        self.assertEqual(c._entity_key(f"{MUSIC}:play_media", "mediakind"),
                         "mediakind", "falls back to the shared list")
        self.assertIsNone(c._entity_key(f"{ALERTS}:change_media", "nosuchslot"))


# T-7245: every constant above is lowercase, which is why the suite could not
# see the round below. ``add_entity`` lowercases the name it stores under and
# ``add_intent`` does not, so a skill id with an uppercase letter composed a
# key no stored key could equal and the slot read as unregistered.

CASED_ALERTS = "skill-Alerts.OpenVoiceOS"


class TestEntityKeyIsCaseFolded(unittest.TestCase):
    def test_a_mixed_case_skill_id_still_resolves_its_list(self):
        """The composed key is folded, as the stored key already was."""
        c = IntentContainer()
        c.add_entity(f"{CASED_ALERTS}:mediakind", ["radio"])
        self.assertEqual(
            c._entity_key(f"{CASED_ALERTS}:change_media", "mediakind"),
            f"{CASED_ALERTS}:mediakind".lower())

    def test_a_mixed_case_skill_id_gates_a_bare_slot(self):
        """The whole point of the list: a member must beat a non-member.

        Both scored the same before, because the lookup missed and every
        captured value took the flat unregistered penalty.
        """
        c = IntentContainer()
        c.add_intent(f"{CASED_ALERTS}:change_media",
                     ["change my alarm to {mediakind}"])
        c.add_entity(f"{CASED_ALERTS}:mediakind", ["music", "radio"])
        member = c.calc_intent("change my alarm to music")["conf"]
        other = c.calc_intent("change my alarm to zzzqqq")["conf"]
        self.assertGreater(member, other,
                           f"member={member} non-member={other}")

    def test_a_mixed_case_skill_id_scores_what_a_lowercase_one_does(self):
        """Case in the skill id must not change a single number."""
        cased = IntentContainer()
        cased.add_intent(f"{CASED_ALERTS}:change_media",
                         ["change my alarm to {mediakind}"])
        cased.add_entity(f"{CASED_ALERTS}:mediakind", ["music"])

        plain = IntentContainer()
        plain.add_intent(f"{CASED_ALERTS.lower()}:change_media",
                         ["change my alarm to {mediakind}"])
        plain.add_entity(f"{CASED_ALERTS.lower()}:mediakind", ["music"])

        for utterance in ("change my alarm to music",
                          "change my alarm to zzzqqq"):
            self.assertEqual(cased.calc_intent(utterance)["conf"],
                             plain.calc_intent(utterance)["conf"],
                             f"case changed the score for {utterance!r}")

    def test_a_mixed_case_entity_name_gates_a_bare_slot(self):
        """The reachable mixed-case name is the entity's, not the slot's.

        ``add_intent`` refuses a slot name outside lowercase letters, digits and
        underscores, so a template cannot carry an author's capital into the
        lookup. An ``add_entity`` caller can, and the fold holds that arm.
        """
        c = IntentContainer()
        c.add_intent(f"{CASED_ALERTS}:change_media",
                     ["change my alarm to {mediakind}"])
        c.add_entity("MediaKind", ["radio"])
        self.assertEqual(sorted(c.entity_samples), ["mediakind"])
        self.assertGreater(c.calc_intent("change my alarm to radio")["conf"],
                           c.calc_intent("change my alarm to zzzqqq")["conf"])

    def test_add_intent_refuses_a_capital_in_a_slot_name(self):
        """Why the bare fold is defence and not a fix: no template reaches it."""
        c = IntentContainer()
        with self.assertRaises(MalformedTemplate):
            c.add_intent("skill.author:change_media",
                         ["change my alarm to {MediaKind}"])
        self.assertEqual(c.intent_samples, {})

    def test_replacing_an_entity_across_case_does_not_keep_both(self):
        """``add_entity`` tested the caller's spelling and stored the folded
        one, so the replacement test could not see what it was replacing."""
        c = IntentContainer()
        c.add_entity("mediakind", ["radio"])
        c.add_entity("MediaKind", ["music"])
        self.assertEqual(sorted(c.entity_samples), ["mediakind"])
        self.assertEqual(c.entity_samples["mediakind"], {"music"})


if __name__ == "__main__":
    unittest.main()
