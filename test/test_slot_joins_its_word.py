"""A slot marker inside a word folds the way the utterance's word folds.

The fold keeps "alarme-inu" one word, "alarmeinu", because a hyphen is a mark
it deletes rather than a word boundary. The Kabyle template
``beddel ales n {schedkind}-inu ...`` must fold to ``{schedkind}inu`` for the
same reason. Folded to ``{schedkind} inu``, it is two words where the
utterance has one, and the template never matches.
"""
import unittest

from padacioso import IntentContainer, _normalize


class TestSlotJoinsItsWord(unittest.TestCase):
    TEMPLATE = "beddel ales n {schedkind}-inu ɣer yal {repeat}"
    UTTERANCE = "beddel ales n alarme-inu ɣer yal ass n ssebt"

    def test_the_template_folds_like_the_utterance(self):
        self.assertEqual(_normalize(self.TEMPLATE).split()[3],
                         _normalize(self.UTTERANCE).split()[3].replace("alarme", "{schedkind}"))

    def test_a_slot_glued_to_a_suffix_matches(self):
        container = IntentContainer()
        container.add_intent("alerts.skill:change_repeat", [self.TEMPLATE])
        match = container.calc_intent(self.UTTERANCE)
        self.assertEqual(match["name"], "alerts.skill:change_repeat")
        self.assertEqual(match["entities"], {"schedkind": "alarme", "repeat": "ass n ssebt"})

    def test_a_separating_mark_still_splits_the_slot_off(self):
        self.assertEqual(_normalize("{name},please"), "{name} please")
