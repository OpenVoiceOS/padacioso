"""Regression test for cross-language intent-unregistration bug.

``handle_register_template`` replaces a prior manifest entry for the
canonical intent name before adding the fresh samples (OVOS-INTENT-4
§8.1 "replacement is implicit"). That replacement must only affect the
language container being (re)registered.

Symptom (verified behaviorally in ovos-skill-ddg#137's CI): a skill
started with ``secondary_langs=["de-DE", "es-ES", "pt-PT"]`` registers
the *same* canonical intent name once per language. Each of those
registrations used to detach the canonical name from *every* configured
language container (not just the one being registered), so only the
last-processed language stayed matchable and the others silently lost
their intent.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso import IntentContainer as FallbackIntentContainer
from padacioso.opm import PadaciosoPipeline

SKILL_ID = "multilang.skill"
INTENT_NAME = "hello"
NEW_NAME = f"{SKILL_ID}:{INTENT_NAME}"
LANGS = ["en-US", "de-DE", "es-ES", "pt-PT"]
SAMPLES = {
    "en-US": ["hello", "hi there"],
    "de-DE": ["hallo", "guten tag"],
    "es-ES": ["hola", "buenos dias"],
    "pt-PT": ["ola", "bom dia"],
}


def register_msg(lang):
    return Message("ovos.intent.register.template", {
        "skill_id": SKILL_ID, "intent_name": INTENT_NAME, "lang": lang,
        "samples": SAMPLES[lang],
    }, {"skill_id": SKILL_ID})


class TestMultilangReregistration(unittest.TestCase):
    def setUp(self):
        self.pipeline = PadaciosoPipeline(FakeBus())
        # simulate a skill configured with secondary_langs=["de-DE", "es-ES", "pt-PT"]
        for lang in LANGS:
            self.pipeline.containers.setdefault(
                lang, FallbackIntentContainer(n_workers=1))

    def test_registering_same_intent_across_langs_keeps_all_langs_matchable(self):
        # register the same canonical intent name once per language, in order,
        # exactly as ovos-workshop does for a multi-lang skill
        for lang in LANGS:
            self.pipeline.handle_register_template(register_msg(lang))

        for lang in LANGS:
            sample = SAMPLES[lang][0]
            intent = self.pipeline.calc_intent([sample], lang=lang)
            self.assertIsNotNone(
                intent,
                f"intent {NEW_NAME!r} should still match in {lang!r} after "
                f"registering the same canonical name in the other langs")
            self.assertEqual(intent.name, NEW_NAME)

        # canonical name is still a single manifest entry, not duplicated
        self.assertEqual(self.pipeline.registered_intents.count(NEW_NAME), 1)

    def test_reregistering_one_lang_does_not_detach_other_langs(self):
        for lang in LANGS:
            self.pipeline.handle_register_template(register_msg(lang))

        # re-register (e.g. skill reload) just the last lang again
        self.pipeline.handle_register_template(register_msg("pt-PT"))

        for lang in LANGS:
            sample = SAMPLES[lang][0]
            intent = self.pipeline.calc_intent([sample], lang=lang)
            self.assertIsNotNone(
                intent, f"{lang!r} lost its match after re-registering pt-PT")


if __name__ == "__main__":
    unittest.main()
