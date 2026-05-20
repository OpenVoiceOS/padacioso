"""End-to-end tests for DomainPadaciosoPipeline using ovoscope.

Drives the standalone domain-padacioso entry point
(`ovos-padacioso-domain-pipeline`) through ovoscope's reusable
:class:`E2EPipelineHarness` and exercises the
``padatious:register_intent`` -> domain routing -> utterance
dispatch path against a :class:`DomainIntentContainer`.
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

from padacioso import DomainIntentContainer  # noqa: E402
from padacioso.opm import DomainPadaciosoPipeline  # noqa: E402

PIPELINE_ID = "ovos-padacioso-domain-pipeline"
CONFIG_KEY = "ovos_padacioso_domain_pipeline"

_LIGHTS_SAMPLES = ["turn on the lights", "switch on lights", "lights on please"]
_DOOR_SAMPLES = ["open the door", "unlock the door"]
_MUSIC_SAMPLES = ["play music", "start the music", "play some {song}"]

SMARTHOME = "smarthome_padacioso"
MEDIA = "media_padacioso"


class _DomainHarness(E2EPipelineHarness):
    PIPELINE_ID = PIPELINE_ID
    CONFIG_KEY = CONFIG_KEY
    PLUGIN_CONFIG = {"fuzz": False}
    SKILL_ID = SMARTHOME

    pipeline: DomainPadaciosoPipeline  # type: ignore[assignment]

    def _register_intent(self, name, samples):
        register_padatious_intent(self.bus, name, samples)

    def _register_entity(self, name, samples):
        register_padatious_entity(self.bus, name, samples)


class TestDomainPipelineLoad(_DomainHarness):
    def test_loaded_with_domain_container(self):
        self.assertIsInstance(self.pipeline, DomainPadaciosoPipeline)
        for lang, container in self.pipeline.containers.items():
            self.assertIsInstance(container, DomainIntentContainer,
                                  f"container for {lang} is not a DomainIntentContainer")


class TestDomainRegistrationRouting(_DomainHarness):
    def test_intents_routed_to_skill_id_domain(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        self._register_intent(f"{MEDIA}:music", _MUSIC_SAMPLES)
        container = next(iter(self.pipeline.containers.values()))
        self.assertIn(SMARTHOME, container.domains)
        self.assertIn(MEDIA, container.domains)
        self.assertIn(f"{SMARTHOME}:lights_on",
                      container.domains[SMARTHOME].intent_samples)
        self.assertIn(f"{MEDIA}:music",
                      container.domains[MEDIA].intent_samples)
        # Parallel-argmax: no top-level router; both domains are live.
        self.assertEqual(set(container.domains), {SMARTHOME, MEDIA})
        detach_skill(self.bus, SMARTHOME)
        detach_skill(self.bus, MEDIA)

    def test_intent_without_namespace_falls_back_to_full_label(self):
        self._register_intent("orphan_label_padacioso", _LIGHTS_SAMPLES)
        container = next(iter(self.pipeline.containers.values()))
        self.assertIn("orphan_label_padacioso", container.domains)
        detach_skill(self.bus, "orphan_label_padacioso")

    def test_detach_intent_removes_only_that_label(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        self._register_intent(f"{SMARTHOME}:door_open", _DOOR_SAMPLES)
        detach_intent(self.bus, f"{SMARTHOME}:lights_on")
        container = next(iter(self.pipeline.containers.values()))
        sub = container.domains[SMARTHOME]
        self.assertNotIn(f"{SMARTHOME}:lights_on", sub.intent_samples)
        self.assertIn(f"{SMARTHOME}:door_open", sub.intent_samples)
        detach_skill(self.bus, SMARTHOME)

    def test_detach_skill_drops_whole_domain(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        self._register_intent(f"{MEDIA}:music", _MUSIC_SAMPLES)
        detach_skill(self.bus, SMARTHOME)
        container = next(iter(self.pipeline.containers.values()))
        self.assertNotIn(SMARTHOME, container.domains)
        self.assertIn(MEDIA, container.domains)
        detach_skill(self.bus, MEDIA)


class TestDomainMatch(_DomainHarness):
    def test_router_picks_correct_domain(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        self._register_intent(f"{MEDIA}:music", _MUSIC_SAMPLES)
        msg = self.send_and_capture(
            "turn on the lights",
            expected_types=[f"{SMARTHOME}:lights_on"],
        )
        self.assertIsNotNone(msg, "expected intent match on bus")
        self.assertEqual(msg.msg_type, f"{SMARTHOME}:lights_on")
        detach_skill(self.bus, SMARTHOME)
        detach_skill(self.bus, MEDIA)

    def test_no_match_unrelated_utterance(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        self.expect_no_match("set a timer for five minutes")
        detach_skill(self.bus, SMARTHOME)

    def test_no_match_when_no_intents_registered(self):
        self.expect_no_match("turn on the lights")


class TestSessionBlacklist(_DomainHarness):
    def test_blacklisted_skill_is_skipped(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        sess = make_session(
            "bl-skill-domain",
            blacklisted_skills=[SMARTHOME],
        )
        self.expect_no_match("turn on the lights", session=sess, timeout=3.0)
        detach_skill(self.bus, SMARTHOME)

    def test_blacklisted_intent_is_skipped(self):
        self._register_intent(f"{SMARTHOME}:lights_on", _LIGHTS_SAMPLES)
        sess = make_session(
            "bl-intent-domain",
            blacklisted_intents=[f"{SMARTHOME}:lights_on"],
        )
        self.expect_no_match("turn on the lights", session=sess, timeout=3.0)
        detach_skill(self.bus, SMARTHOME)


if __name__ == "__main__":
    unittest.main()
