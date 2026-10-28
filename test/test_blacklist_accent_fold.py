"""A blacklist line is folded exactly like the utterance it is compared with.

The container folds the query (lowercase, diacritics stripped). A blacklist
line must go through the same fold, otherwise an accented line such as
"às 6" never suppresses anything, not even the identical utterance.
OVOS-INTENT-2 4.3 still applies after the fold: a phrase occurs as a
contiguous sequence of whole words.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso import IntentContainer
from padacioso.opm import PadaciosoPipeline

PT_SAMPLE = "me acorda às 6 horas"
ES_SAMPLE = "tengo {n} días libres"
FR_SAMPLE = "je vais {x}"


def matched(sample, line, utterance):
    container = IntentContainer()
    container.add_intent("it", [sample])
    container.exclude_keywords("it", [line])
    return container.calc_intent(utterance)["name"] == "it"


class TestBlacklistAccentFold(unittest.TestCase):
    def test_accented_line_suppresses_accented_and_plain_utterance(self):
        self.assertFalse(matched(PT_SAMPLE, "às 6", "me acorda às 6 horas"))
        self.assertFalse(matched(PT_SAMPLE, "às 6", "me acorda as 6 horas"))

    def test_plain_line_suppresses_accented_and_plain_utterance(self):
        self.assertFalse(matched(PT_SAMPLE, "as 6", "me acorda às 6 horas"))
        self.assertFalse(matched(PT_SAMPLE, "as 6", "me acorda as 6 horas"))

    def test_upper_case_accented_line(self):
        self.assertFalse(matched(PT_SAMPLE, "ÀS 6", "me acorda as 6 horas"))

    def test_spanish_accented_line(self):
        self.assertFalse(matched(ES_SAMPLE, "días", "tengo 3 días libres"))
        self.assertFalse(matched(ES_SAMPLE, "días", "tengo 3 dias libres"))
        self.assertFalse(matched(ES_SAMPLE, "dias", "tengo 3 días libres"))

    def test_french_accented_line(self):
        self.assertFalse(matched(FR_SAMPLE, "à", "je vais à paris"))
        self.assertFalse(matched(FR_SAMPLE, "à", "je vais a paris"))

    def test_line_does_not_occur_inside_a_word(self):
        self.assertTrue(matched("quero {x}", "às", "quero mais"))
        self.assertTrue(matched("quero {x}", "às", "quero casas"))
        self.assertTrue(matched("quero {x}", "às 6", "quero mas 6"))
        self.assertTrue(matched(FR_SAMPLE, "à", "je vais cabane"))

    def test_control_line_leaves_intent_matching(self):
        self.assertTrue(matched(PT_SAMPLE, "zzz", "me acorda às 6 horas"))
        self.assertTrue(matched(PT_SAMPLE, "às 7", "me acorda às 6 horas"))

    def test_registered_list_is_not_mutated(self):
        lines = ["às 6"]
        container = IntentContainer()
        container.exclude_keywords("it", lines)
        self.assertEqual(lines, ["às 6"])


class TestSlotBlacklistAccentFold(unittest.TestCase):
    def pipeline(self, blacklisted):
        pipeline = PadaciosoPipeline(FakeBus())
        pipeline.containers.setdefault("pt-BR", IntentContainer(n_workers=1))
        pipeline.handle_register_template(Message(
            "ovos.intent.register.template", {
                "skill_id": "s.skill", "intent_name": "i", "lang": "pt-BR",
                "samples": ["fala {word}"],
                "slot_blacklist": {"word": [blacklisted]},
            }, {"skill_id": "s.skill"}))
        return pipeline

    def bound(self, blacklisted, utterance):
        intent = self.pipeline(blacklisted).calc_intent([utterance], lang="pt-BR")
        self.assertIsNotNone(intent)
        return intent.matches.get("word")

    def test_accented_slot_line_rejects_plain_value(self):
        self.assertIsNone(self.bound("às", "fala as"))
        self.assertIsNone(self.bound("às", "fala às"))

    def test_plain_slot_line_rejects_accented_value(self):
        self.assertIsNone(self.bound("as", "fala às"))

    def test_other_value_still_binds(self):
        self.assertEqual(self.bound("às", "fala casas"), "casas")


if __name__ == "__main__":
    unittest.main()
