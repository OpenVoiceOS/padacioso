"""Registration-time alias collapse and blacklist canonicalization.

ovos-workshop >= 9.3 dual-registers one logical intent under both the
legacy ``<skill_id>:<file>.intent`` id (via ``padatious:register_intent``)
and the OVOS-INTENT-4 canonical ``<skill_id>:<file>`` id (via
``ovos.intent.register.template`` -> ``handle_register_template``). This
plugin owns collapsing that alias at REGISTRATION time so both wire
contracts land as a single engine entry (ovos-core#831).

These tests cover:
- both registration messages collapse to exactly one manifest entry
- detaching by the legacy name removes the collapsed entry
- the session blacklist filter still canonicalizes legacy-named entries
  (since old sessions/config may carry them) and warns once per entry
"""
import unittest
from unittest import mock

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline, _warned_legacy_blacklist_entries

SKILL_ID = "collapse.skill"
LEGACY_NAME = f"{SKILL_ID}:hello.intent"
NEW_NAME = f"{SKILL_ID}:hello"
LANG = "en-US"
SAMPLES = ["hello", "hi there", "hey"]


def legacy_register_msg():
    return Message("padatious:register_intent", {
        "skill_id": SKILL_ID, "name": LEGACY_NAME, "lang": LANG,
        "samples": SAMPLES,
    }, {"skill_id": SKILL_ID})


def spec_register_msg():
    return Message("ovos.intent.register.template", {
        "skill_id": SKILL_ID, "intent_name": "hello", "lang": LANG,
        "samples": SAMPLES,
    }, {"skill_id": SKILL_ID})


class TestRegistrationCollapse(unittest.TestCase):
    def setUp(self):
        self.pipeline = PadaciosoPipeline(FakeBus())

    def test_both_wire_contracts_collapse_to_one_manifest_entry(self):
        self.pipeline.register_intent(legacy_register_msg())
        self.pipeline.handle_register_template(spec_register_msg())

        manifest = self.pipeline.registered_intents
        self.assertEqual(manifest.count(NEW_NAME), 1)
        self.assertNotIn(LEGACY_NAME, manifest)

    def test_second_arrival_replaces_not_duplicates_engine_entry(self):
        self.pipeline.register_intent(legacy_register_msg())
        self.pipeline.handle_register_template(spec_register_msg())

        container = self.pipeline.containers[LANG]
        # engine keys intents by name in a dict, so re-registration is
        # inherently a replace; assert there's exactly one entry present
        self.assertIn(NEW_NAME, container.intent_samples)
        self.assertNotIn(LEGACY_NAME, container.intent_samples)

    def test_detach_by_legacy_name_removes_collapsed_entry(self):
        self.pipeline.register_intent(legacy_register_msg())
        self.pipeline.handle_register_template(spec_register_msg())
        self.assertIn(NEW_NAME, self.pipeline.registered_intents)

        self.pipeline.handle_detach_intent(
            Message("detach_intent", {"intent_name": LEGACY_NAME}))

        self.assertNotIn(NEW_NAME, self.pipeline.registered_intents)
        self.assertNotIn(NEW_NAME, self.pipeline.containers[LANG].intent_samples)


class TestSessionBlacklistCanonicalization(unittest.TestCase):
    """Matches are canonical by construction; only the blacklist entries
    (which may still carry legacy-named sessions) need canonicalizing."""

    def setUp(self):
        _warned_legacy_blacklist_entries.clear()
        self.pipeline = PadaciosoPipeline(FakeBus())
        self.pipeline.register_intent(legacy_register_msg())
        self.pipeline.handle_register_template(spec_register_msg())

    def test_legacy_named_blacklist_entry_suppresses_canonical_match(self):
        sess = mock.Mock()
        sess.blacklisted_intents = [LEGACY_NAME]
        sess.blacklisted_skills = []
        sess.intent_context = {}
        with mock.patch("padacioso.opm.SessionManager.get", return_value=sess):
            intent = self.pipeline.calc_intent(["hello"], lang=LANG)
        self.assertIsNone(intent)

    def test_legacy_named_blacklist_entry_logs_deprecation_warning_once(self):
        sess = mock.Mock()
        sess.blacklisted_intents = [LEGACY_NAME]
        sess.blacklisted_skills = []
        sess.intent_context = {}
        from padacioso.opm import _calc_padacioso_intent
        _calc_padacioso_intent.cache_clear()
        with mock.patch("padacioso.opm.SessionManager.get", return_value=sess), \
                mock.patch("padacioso.opm.LOG.warning") as mock_warn:
            self.pipeline.calc_intent(["hello"], lang=LANG)
            self.pipeline.calc_intent(["hi there"], lang=LANG)

        deprecation_calls = [c for c in mock_warn.call_args_list
                             if LEGACY_NAME in str(c)]
        self.assertEqual(len(deprecation_calls), 1)
        self.assertIn(NEW_NAME, str(deprecation_calls[0]))


if __name__ == "__main__":
    unittest.main()
