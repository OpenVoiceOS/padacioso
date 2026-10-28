"""An entity value matches the slot whatever diacritics the skill spelled.

The matcher captures slot values from the query as ``_normalize`` folds it, so
"toca música" captures "musica". The entity lists "música". Compared unfolded,
the value the user said is no member and the match loses the member score to
any rival whose slots hold no entity at all.
"""
import unittest

from padacioso import IntentContainer

SKILL = "alerts.skill"


class TestEntityMemberFolds(unittest.TestCase):
    def _conf(self, utterance, values):
        container = IntentContainer()
        container.add_intent(f"{SKILL}:play", ["toca {mediakind}"])
        container.add_entity(f"{SKILL}:mediakind", values)
        matches = list(container.calc_intents(utterance))
        self.assertEqual(len(matches), 1)
        return matches[0]["conf"]

    def test_an_accented_value_is_a_member(self):
        self.assertEqual(self._conf("toca música", ["música"]),
                         self._conf("toca jazz", ["jazz"]),
                         "a listed accented value must score as a member")

    def test_an_unlisted_value_is_still_no_member(self):
        self.assertLess(self._conf("toca rádio", ["música"]),
                        self._conf("toca música", ["música"]))

    def test_the_slot_keeps_the_spoken_surface(self):
        container = IntentContainer()
        container.add_intent(f"{SKILL}:play", ["toca {mediakind}"])
        container.add_entity(f"{SKILL}:mediakind", ["música"])
        match = next(container.calc_intents("toca Música"))
        self.assertEqual(match["entities"]["mediakind"], "Música")

    def test_a_replaced_entity_forgets_its_old_values(self):
        container = IntentContainer()
        container.add_intent(f"{SKILL}:play", ["toca {mediakind}"])
        container.add_entity(f"{SKILL}:mediakind", ["música"])
        member = next(container.calc_intents("toca música"))["conf"]
        container.add_entity(f"{SKILL}:mediakind", ["rádio"])
        self.assertLess(next(container.calc_intents("toca música"))["conf"], member)
