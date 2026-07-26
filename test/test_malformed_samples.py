"""Malformed template samples must never crash intent registration.

OVOS-INTENT-4 §6.3/§5.3: consumers skip malformed samples with a warning
(naming skill, intent, lang, topic and reason), index the remaining valid
samples, and reject the registration only when no valid sample remains —
the executor never crashes.
"""
import unittest
from unittest import mock

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline


def _pipeline():
    return PadaciosoPipeline(FakeBus(), {"fuzz": False})


class LegacyRegistrationMalformedSamplesTest(unittest.TestCase):
    """Legacy ``padatious:register_intent`` path."""

    def _register(self, pipeline, samples,
                  name='skill-persona.openvoiceos:cancel.intent'):
        pipeline.register_intent(Message('padatious:register_intent',
                                         {'name': name,
                                          'lang': 'en-US',
                                          'samples': samples}))

    def test_malformed_sample_skipped_valid_indexed(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            # slot-only and unbalanced samples ride along a valid one,
            # as in released locale files with translated slot names
            self._register(pipeline, ['{utterance}',
                                      'cancel {rotina',
                                      'stop everything'])
        self.assertEqual(warn.call_count, 2)
        container = pipeline.containers['en-US']
        # registration-time alias collapse (ovos-core#831) canonicalizes the
        # legacy `.intent`-suffixed name before indexing
        name = 'skill-persona.openvoiceos:cancel'
        self.assertIn(name, container.intent_samples)
        result = container.calc_intent('stop everything')
        self.assertEqual(result['name'], name)

    def test_all_samples_malformed_rejects_registration(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            self._register(pipeline, ['{utterance}', '{other}'])
        self.assertTrue(warn.called)
        container = pipeline.containers['en-US']
        name = 'skill-persona.openvoiceos:cancel.intent'
        self.assertNotIn(name, container.intent_samples)
        self.assertNotIn(name, pipeline.registered_intents)

    def test_warning_names_skill_intent_lang_topic(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            self._register(pipeline, ['{utterance}', 'stop everything'])
        logged = " ".join(str(c) for c in warn.call_args_list)
        # the warning names the canonical (alias-collapsed) intent name,
        # since registration-time collapse happens before this log fires
        for token in ('skill-persona.openvoiceos', 'cancel',
                      'en-US', 'padatious:register_intent'):
            self.assertIn(token, logged)

    def test_legacy_entity_malformed_sample_skipped(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            pipeline.register_entity(
                Message('padatious:register_entity',
                        {'name': 'skill-persona.openvoiceos:thing',
                         'lang': 'en-US',
                         'samples': ['ok value', 'broken {value']}))
        self.assertEqual(warn.call_count, 1)
        container = pipeline.containers['en-US']
        self.assertIn('skill-persona.openvoiceos:thing',
                      container.entity_samples)


class SpecRegistrationMalformedSamplesTest(unittest.TestCase):
    """INTENT-4 ``ovos.intent.register.template`` / entity paths."""

    def test_template_malformed_sample_skipped(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            pipeline.handle_register_template(
                Message('ovos.intent.register.template',
                        {'skill_id': 'skill-persona.openvoiceos',
                         'intent_name': 'cancel',
                         'lang': 'en-US',
                         'samples': ['{utterance}', 'stop everything']}))
        self.assertEqual(warn.call_count, 1)
        name = pipeline._internal_name('skill-persona.openvoiceos', 'cancel')
        self.assertIn(name, pipeline.containers['en-US'].intent_samples)

    def test_template_all_malformed_rejected(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            pipeline.handle_register_template(
                Message('ovos.intent.register.template',
                        {'skill_id': 'skill-persona.openvoiceos',
                         'intent_name': 'cancel',
                         'lang': 'en-US',
                         'samples': ['{utterance}']}))
        self.assertTrue(warn.called)
        name = pipeline._internal_name('skill-persona.openvoiceos', 'cancel')
        self.assertNotIn(name, pipeline.containers['en-US'].intent_samples)
        self.assertNotIn(name, pipeline.registered_intents)

    def test_entity_malformed_sample_skipped(self):
        pipeline = _pipeline()
        with mock.patch('padacioso.opm.LOG.warning') as warn:
            pipeline.handle_register_entity(
                Message('ovos.entity.register',
                        {'skill_id': 'skill-persona.openvoiceos',
                         'entity_name': 'thing',
                         'lang': 'en-US',
                         'samples': ['broken {value', 'good value']}))
        self.assertEqual(warn.call_count, 1)
        name = pipeline._internal_name('skill-persona.openvoiceos', 'thing')
        self.assertIn(name, pipeline.containers['en-US'].entity_samples)


if __name__ == '__main__':
    unittest.main()
