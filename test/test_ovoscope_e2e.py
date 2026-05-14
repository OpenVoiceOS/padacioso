"""End-to-end tests for PadaciosoPipeline using ovoscope.

Built on top of ovoscope's reusable :class:`E2EPipelineHarness` so this
file only contains padacioso-specific concerns (sample-based intent +
entity registration via the `padatious:register_*` bus events).
"""
import unittest

import pytest

ovoscope = pytest.importorskip("ovoscope", reason="ovoscope not installed; skipping E2E tests")

from ovoscope import (  # noqa: E402
    E2EPipelineHarness,
    detach_intent,
    detach_skill,
    make_session,
    register_padatious_entity,
    register_padatious_intent,
)

from padacioso.opm import PadaciosoPipeline  # noqa: E402

PIPELINE_ID = "ovos-padacioso-pipeline-plugin"
CONFIG_KEY = "padacioso"

_HELLO_SAMPLES = ["hello", "hi", "hey", "greetings", "good morning"]
_BYE_SAMPLES = ["goodbye", "bye", "see you later", "farewell", "take care"]
_LIGHTS_ON_SAMPLES = ["turn on the lights", "switch on lights", "lights on please"]


class _PadaciosoHarness(E2EPipelineHarness):
    PIPELINE_ID = PIPELINE_ID
    CONFIG_KEY = CONFIG_KEY
    PLUGIN_CONFIG = {"fuzz": True}
    SKILL_ID = "test_skill_padacioso"

    pipeline: PadaciosoPipeline  # type: ignore[assignment]

    def _register_intent(self, name, samples):
        register_padatious_intent(self.bus, name, samples)

    def _register_entity(self, name, samples):
        register_padatious_entity(self.bus, name, samples)


class TestRegisteredIntentMatch(_PadaciosoHarness):
    def test_exact_utterance_dispatches_intent(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        msg = self.send_and_capture("hello", expected_types=[f"{self.SKILL_ID}:hello"])
        self.assertIsNotNone(msg, "expected intent match on bus")
        self.assertEqual(msg.msg_type, f"{self.SKILL_ID}:hello")
        self.assertEqual(msg.data.get("utterance"), "hello")

    def test_no_match_when_no_intents_registered(self):
        self.expect_no_match("hello")

    def test_no_match_unrelated_utterance(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        self.expect_no_match("set a timer for five minutes")

    def test_best_intent_selected_among_multiple(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        self._register_intent(f"{self.SKILL_ID}:bye", _BYE_SAMPLES)
        msg = self.send_and_capture("goodbye", expected_types=[f"{self.SKILL_ID}:bye"])
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, f"{self.SKILL_ID}:bye")


class TestEntityExtraction(_PadaciosoHarness):
    def test_entity_slot_captured_in_match(self):
        self._register_entity("item", ["milk", "bread", "eggs", "cheese"])
        self._register_intent(
            f"{self.SKILL_ID}:buy",
            ["buy {item}", "get {item}", "purchase {item}"],
        )
        msg = self.send_and_capture("buy milk", expected_types=[f"{self.SKILL_ID}:buy"])
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_type, f"{self.SKILL_ID}:buy")


class TestDetach(_PadaciosoHarness):
    def test_detach_intent_prevents_match(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        msg = self.send_and_capture("hello", expected_types=[f"{self.SKILL_ID}:hello"])
        self.assertIsNotNone(msg)

        detach_intent(self.bus, f"{self.SKILL_ID}:hello")
        self.expect_no_match("hello")

    def test_detach_skill_removes_all_its_intents(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        self._register_intent(f"{self.SKILL_ID}:bye", _BYE_SAMPLES)
        self._register_intent("skill_b_padacioso:lights_on", _LIGHTS_ON_SAMPLES)

        detach_skill(self.bus, self.SKILL_ID)

        self.expect_no_match("hello")
        self.expect_no_match("goodbye")
        msg = self.send_and_capture(
            "turn on the lights", expected_types=["skill_b_padacioso:lights_on"]
        )
        self.assertIsNotNone(msg, "skill_b intent should survive skill_a detach")
        detach_skill(self.bus, "skill_b_padacioso")


class TestSessionBlacklist(_PadaciosoHarness):
    def test_blacklisted_intent_is_skipped(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        sess = make_session(
            "bl-intent-test",
            blacklisted_intents=[f"{self.SKILL_ID}:hello"],
        )
        self.expect_no_match("hello", session=sess, timeout=3.0)

    def test_blacklisted_skill_is_skipped(self):
        self._register_intent(f"{self.SKILL_ID}:hello", _HELLO_SAMPLES)
        sess = make_session(
            "bl-skill-test",
            blacklisted_skills=[self.SKILL_ID],
        )
        self.expect_no_match("hello", session=sess, timeout=3.0)


if __name__ == "__main__":
    unittest.main()
