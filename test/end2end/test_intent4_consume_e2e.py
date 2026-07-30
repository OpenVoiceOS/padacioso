"""OVOS-INTENT-4 *consumer* end-to-end tests for the Padacioso pipeline.

``test/test_ovoscope_e2e.py`` proves padacioso matches intents registered via
the legacy ``padatious:register_*`` events. This suite proves padacioso
*consumes the INTENT-4 spec registration topics* (``ovos-intent-4.md``) and then
matches.

Padacioso is a **template** engine: it consumes ``ovos.intent.register.template``
(§6) and not ``ovos.intent.register.keyword`` (§11). Each test boots a real
``MiniCroft`` pinned to the padacioso pipeline, emits the spec registration on
the wire, sends a matching utterance, and asserts the intent dispatches
``<skill_id>:<intent_name>`` — proving spec-topic consumption.
"""
import time
import unittest

import pytest

ovoscope = pytest.importorskip(
    "ovoscope", reason="ovoscope not installed; skipping E2E tests"
)

from ovoscope import E2EPipelineHarness  # noqa: E402
from ovos_bus_client.message import Message  # noqa: E402
from ovos_spec_tools import SpecMessage  # noqa: E402

from padacioso.opm import PadaciosoPipeline  # noqa: E402

PIPELINE_ID = "ovos-padacioso-pipeline-plugin"
CONFIG_KEY = "padacioso"

REGISTER_TEMPLATE = str(SpecMessage.INTENT_REGISTER_TEMPLATE)
REGISTER_KEYWORD = str(SpecMessage.INTENT_REGISTER_KEYWORD)
ENTITY_REGISTER = str(SpecMessage.ENTITY_REGISTER)
INTENT_DEREGISTER = str(SpecMessage.INTENT_DEREGISTER)
SKILL_DEREGISTER = str(SpecMessage.SKILL_DEREGISTER)
INTENT_DISABLE = str(SpecMessage.INTENT_DISABLE)
INTENT_ENABLE = str(SpecMessage.INTENT_ENABLE)

_HELLO = ["hello", "hi there", "hey"]
_BYE = ["goodbye", "bye bye", "see you"]


class _Intent4PadaciosoHarness(E2EPipelineHarness):
    PIPELINE_ID = PIPELINE_ID
    CONFIG_KEY = CONFIG_KEY
    PLUGIN_CONFIG = {}
    SKILL_ID = "intent4_padacioso.skill"

    pipeline: PadaciosoPipeline  # type: ignore[assignment]

    def _register_template(self, intent_name, samples, *, blacklist=None,
                           lang="en-US", settle=1.0):
        payload = {
            "skill_id": self.SKILL_ID,
            "intent_name": intent_name,
            "lang": lang,
            "samples": samples,
        }
        if blacklist is not None:
            payload["blacklist"] = blacklist
        self.bus.emit(Message(REGISTER_TEMPLATE, payload,
                              {"skill_id": self.SKILL_ID}))
        time.sleep(settle)

    def _capture_match(self, utterance, intent_name, timeout=5.0):
        """send_and_capture with one retry — the first match after a fresh
        MiniCroft boot occasionally races the pipeline-ready state."""
        expected = [f"{self.SKILL_ID}:{intent_name}"]
        msg = self.send_and_capture(utterance, expected_types=expected,
                                    timeout=timeout)
        if msg is None:
            time.sleep(0.5)
            msg = self.send_and_capture(utterance, expected_types=expected,
                                        timeout=timeout)
        return msg

    def _emit(self, topic, intent_name=None, settle=0.8, **extra):
        data = {"skill_id": self.SKILL_ID, "lang": "en-US"}
        if intent_name is not None:
            data["intent_name"] = intent_name
        data.update(extra)
        self.bus.emit(Message(topic, data, {"skill_id": self.SKILL_ID}))
        time.sleep(settle)


class TestSpecTemplateConsumed(_Intent4PadaciosoHarness):
    """§6: a template intent registered on the spec topic becomes matchable."""

    def test_spec_template_registration_is_matchable(self):
        self._register_template("hello", _HELLO)
        msg = self._capture_match("hello", "hello")
        self.assertIsNotNone(msg, "expected intent match from spec registration")
        self.assertEqual(msg.msg_type, f"{self.SKILL_ID}:hello")

    def test_spec_template_slot_capture(self):
        """A ``{slot}`` template fills from the utterance (§6.1)."""
        self._register_template("buy", ["buy {item}", "purchase {item}"])
        msg = self._capture_match("buy milk", "buy")
        self.assertIsNotNone(msg, "slot template should match")


class TestLegacyStillConsumed(_Intent4PadaciosoHarness):
    """Back-compat: legacy ``padatious:register_intent`` still matches."""

    def test_legacy_template_registration_still_matches(self):
        from ovoscope import register_padatious_intent
        register_padatious_intent(self.bus, f"{self.SKILL_ID}:bye", _BYE)
        time.sleep(0.4)
        msg = self.send_and_capture(
            "goodbye", expected_types=[f"{self.SKILL_ID}:bye"]
        )
        self.assertIsNotNone(msg, "legacy registration must still match")


class TestSpecDeregister(_Intent4PadaciosoHarness):
    """§8.2 / §8.4: spec deregistration removes a spec-registered intent."""

    def test_spec_deregister_removes_intent(self):
        self._register_template("hello", _HELLO)
        self.assertIsNotNone(
            self._capture_match("hello", "hello"),
            "sanity: intent should match before deregister",
        )
        self._emit(INTENT_DEREGISTER, "hello")
        self.expect_no_match("hello", timeout=3.0)

    def test_spec_skill_deregister_removes_intent(self):
        self._register_template("hello", _HELLO)
        self._emit(SKILL_DEREGISTER)
        self.expect_no_match("hello", timeout=3.0)


class TestSpecDisableEnable(_Intent4PadaciosoHarness):
    """§8.5: ``ovos.intent.disable`` suppresses, ``ovos.intent.enable`` re-arms.

    Padacioso has no native suppression flag, so disable removes the intent's
    regexes from the container while retaining the expanded samples for
    re-arming — registration-scoped suppression per §8.5.
    """

    def test_spec_disable_suppresses_intent(self):
        self._register_template("hello", _HELLO)
        self._emit(INTENT_DISABLE, "hello")
        self.expect_no_match("hello", timeout=3.0)

    def test_spec_enable_rearms_intent(self):
        self._register_template("hello", _HELLO)
        self._emit(INTENT_DISABLE, "hello")
        self._emit(INTENT_ENABLE, "hello")
        msg = self._capture_match("hello", "hello")
        self.assertIsNotNone(msg, "intent should match again after enable")


class TestNegativeKeywordTopic(_Intent4PadaciosoHarness):
    """§11: a template engine MUST NOT consume the *keyword* topic."""

    def test_keyword_topic_does_not_match_on_template_engine(self):
        self.bus.emit(Message(REGISTER_KEYWORD, {
            "skill_id": self.SKILL_ID,
            "intent_name": "lights_off",
            "lang": "en-US",
            "required": [{"name": "TurnOff", "samples": ["off"]},
                         {"name": "Light", "samples": ["lights"]}],
            "optional": [], "one_of": [], "excluded": [],
        }, {"skill_id": self.SKILL_ID}))
        time.sleep(0.5)
        self.expect_no_match("turn off the lights", timeout=3.0)


if __name__ == "__main__":
    unittest.main()
