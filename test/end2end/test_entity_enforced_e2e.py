"""T-7201: a skill's ``.entity`` value set must actually gate a slot, on a real bus.

The pipeline plugin registers an entity under ``<skill_id>:<entity_name>``,
because two skills may each declare a ``mediakind`` and one must not answer for
the other. The matcher looked the slot up under its BARE template name, so no
registered value set was ever found: every captured value took the flat
"unregistered" penalty, a value in the list scored no better than a typo, and a
template ending in a free slot absorbed any tail.

The samples and value sets below are ovos-skill-alerts' real en-US resources,
read from ``origin/dev``: ``change_media_properties`` and ``reschedule_alert``
are the pair the field report named, and ``mediakind`` is the list that should
separate them.
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

REGISTER_TEMPLATE = str(SpecMessage.INTENT_REGISTER_TEMPLATE)
ENTITY_REGISTER = str(SpecMessage.ENTITY_REGISTER)

# ovos-skill-alerts locale/en-US, trimmed to the lines this pair needs
_CHANGE_MEDIA = [
    "(change|set|adjust|make) (my|the|my next|the next|my upcoming) {schedkind} to play {mediakind}",
    "(change|set|adjust|make) (my|the|my next|the next) {schedkind} to {mediakind}",
]
_RESCHEDULE = [
    "(move|change|reschedule|shift|push|postpone|adjust) (my|the) {schedkind} (to|until|for) {time}",
]
_MEDIAKIND = ["music", "radio", "news", "podcast", "audiobook", "video"]
_SCHEDKIND = ["alarm", "alarms", "timer", "reminder", "event"]


class TestEntityListGatesTheSlot(E2EPipelineHarness):
    PIPELINE_ID = "ovos-padacioso-pipeline-plugin"
    CONFIG_KEY = "padacioso"
    PLUGIN_CONFIG = {}
    SKILL_ID = "skill-alerts.openvoiceos"

    pipeline: PadaciosoPipeline  # type: ignore[assignment]

    def _register(self):
        for name, samples in (("change_media_properties", _CHANGE_MEDIA),
                              ("reschedule_alert", _RESCHEDULE)):
            self.bus.emit(Message(REGISTER_TEMPLATE, {
                "skill_id": self.SKILL_ID, "intent_name": name,
                "lang": "en-US", "samples": samples},
                {"skill_id": self.SKILL_ID}))
        for name, samples in (("mediakind", _MEDIAKIND),
                              ("schedkind", _SCHEDKIND)):
            self.bus.emit(Message(ENTITY_REGISTER, {
                "skill_id": self.SKILL_ID, "entity_name": name,
                "lang": "en-US", "samples": samples},
                {"skill_id": self.SKILL_ID}))
        time.sleep(1.2)

    def _conf(self, utterance, intent_name):
        """The pipeline's own confidence for one intent, off the live container."""
        container = self.pipeline.containers["en-US"]
        for row in container.calc_intents(utterance):
            if row["name"] == f"{self.SKILL_ID}:{intent_name}":
                return row["conf"]
        return None

    def test_the_entity_list_is_registered_under_the_skill_namespace(self):
        """The premise, asserted rather than assumed: this is the spelling the
        matcher has to resolve."""
        self._register()
        keys = set(self.pipeline.containers["en-US"].entity_samples)
        self.assertIn(f"{self.SKILL_ID}:mediakind", keys)
        self.assertNotIn("mediakind", keys)

    def test_a_value_in_the_list_outscores_a_value_that_is_not(self):
        """The defect: both scored the same, so the list enforced nothing."""
        self._register()
        member = self._conf("change my alarm to play music", "change_media_properties")
        typo = self._conf("change my alarm to play zzzqqq", "change_media_properties")
        self.assertIsNotNone(member, "the member utterance must match at all")
        self.assertIsNotNone(typo, "the typo utterance still matches the template")
        self.assertGreater(
            member, typo,
            "a registered mediakind must outscore a value the skill never declared; "
            f"member={member} typo={typo}")

    def test_the_free_slot_no_longer_absorbs_a_time(self):
        """A time belongs to reschedule_alert. While the list enforced nothing,
        change_media_properties tied with it and won on order."""
        self._register()
        media = self._conf("change my alarm to 7 am", "change_media_properties")
        reschedule = self._conf("change my alarm to 7 am", "reschedule_alert")
        self.assertIsNotNone(reschedule, "reschedule_alert must match a time")
        self.assertGreater(
            reschedule, media,
            "a time must not score as a mediakind; "
            f"reschedule={reschedule} media={media}")

    def test_a_member_still_dispatches(self):
        """The control: the fix must not stop a real value from matching."""
        self._register()
        msg = self.send_and_capture(
            "change my alarm to play music",
            expected_types=[f"{self.SKILL_ID}:change_media_properties"],
            timeout=5.0)
        if msg is None:
            time.sleep(0.5)
            msg = self.send_and_capture(
                "change my alarm to play music",
                expected_types=[f"{self.SKILL_ID}:change_media_properties"],
                timeout=5.0)
        self.assertIsNotNone(msg, "a declared mediakind must still dispatch")


if __name__ == "__main__":
    unittest.main()
