"""Regression test for per-language slot blacklists.

OVOS-INTENT-2 §4.3 per-slot value blacklists are registered per language:
``ovos_workshop.skills.ovos.py``'s ``register_intent_file`` loops
``for lang in self.native_langs`` and calls ``register_template`` once per
language, passing that language's own ``word.blacklist`` values. The engine
used to key its blacklist store by intent name alone, so each language's
registration overwrote the previous one and only the last-registered
language's blacklist survived for every language.

Symptom (ovos-skill-spelling#53): adding it-IT/nl-NL/pt-BR/sv-SE locales made
the en-US utterance "spell it" bind the pronoun literally, because the
surviving blacklist was pt-BR's (or whichever language registered last), not
English's.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso import IntentContainer as FallbackIntentContainer
from padacioso.opm import PadaciosoPipeline

SKILL_ID = "spelling.skill"
INTENT_NAME = "spell"
NEW_NAME = f"{SKILL_ID}:{INTENT_NAME}"


def register_msg(lang, blacklist_word):
    return Message("ovos.intent.register.template", {
        "skill_id": SKILL_ID, "intent_name": INTENT_NAME, "lang": lang,
        "samples": ["spell {word}"],
        "slot_blacklist": {"word": [blacklist_word]},
    }, {"skill_id": SKILL_ID})


class TestSlotBlacklistPerLang(unittest.TestCase):
    def setUp(self):
        self.pipeline = PadaciosoPipeline(FakeBus())
        for lang in ("en-US", "pt-PT"):
            self.pipeline.containers.setdefault(
                lang, FallbackIntentContainer(n_workers=1))
        # en-US registers first, pt-PT second, mirroring a multi-lang skill's
        # native_langs registration loop
        self.pipeline.handle_register_template(register_msg("en-US", "it"))
        self.pipeline.handle_register_template(register_msg("pt-PT", "isso"))

    def test_each_lang_keeps_its_own_blacklist(self):
        # en-US's own blacklisted pronoun ("it") must still be rejected after
        # pt-PT registered later with a different blacklist
        intent = self.pipeline.calc_intent(["spell it"], lang="en-US")
        self.assertIsNotNone(intent)
        self.assertNotIn("word", intent.matches)

        # pt-PT's blacklisted pronoun ("isso") is likewise rejected
        intent = self.pipeline.calc_intent(["spell isso"], lang="pt-PT")
        self.assertIsNotNone(intent)
        self.assertNotIn("word", intent.matches)

        # a value not on en-US's blacklist (pt-PT's word) still binds normally
        # in en-US, proving the two languages' blacklists are independent
        intent = self.pipeline.calc_intent(["spell isso"], lang="en-US")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.matches.get("word"), "isso")


if __name__ == "__main__":
    unittest.main()
