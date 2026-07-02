import unittest

from ovos_utils.messagebus import FakeBus

from ovos_bus_client.message import Message
from padacioso import IntentContainer
from padacioso.opm import PadaciosoPipeline


class UtteranceIntentMatchingTest(unittest.TestCase):
    def get_service(self, fuzz=True):
        intent_service = PadaciosoPipeline(FakeBus(), {"fuzz": fuzz})
        # register test intents
        filename = "/tmp/test.intent"
        with open(filename, "w") as f:
            f.write("this is a test\ntest the intent\nexecute test")
        rxfilename = "/tmp/test2.intent"
        with open(rxfilename, "w") as f:
            f.write("tell me about {thing}\nwhat is {thing}")
        data = {'file_name': filename, 'lang': 'en-US', 'name': 'test'}
        intent_service.register_intent(Message("padatious:register_intent", data))
        data = {'file_name': rxfilename, 'lang': 'en-US', 'name': 'test2'}
        intent_service.register_intent(Message("padatious:register_intent", data))
        return intent_service

    def test_padacioso_intent(self):
        intent_service = self.get_service(fuzz=False)

        for container in intent_service.containers.values():
            self.assertIsInstance(container, IntentContainer)

        # exact match
        intent = intent_service.calc_intent("this is a test", "en-US")
        self.assertEqual(intent.name, "test")

        # fuzzy match - failure case
        intent = intent_service.calc_intent("this test", "en-US")
        self.assertIsNone(intent)

        # regex match
        intent = intent_service.calc_intent("tell me about Mycroft", "en-US")
        self.assertEqual(intent.name, "test2")
        # entity values are normalized (lowercased) for matching per OVOS-INTENT-1
        self.assertEqual(intent.matches, {'thing': 'mycroft'})

        # fuzzy regex match - failure case
        utterance = "tell me everything about Mycroft"
        intent = intent_service.calc_intent(utterance, "en-US")
        self.assertIsNone(intent)

    def test_padacioso_fuzz_intent(self):
        intent_service = self.get_service(fuzz=True)

        # fuzzy match - success
        intent = intent_service.calc_intent("this is test", "en-US")
        self.assertEqual(intent.name, "test")
        self.assertTrue(intent.conf <= 0.8)

        # fuzzy regex match - success
        utterance = "tell me everything about Mycroft"
        intent = intent_service.calc_intent(utterance, "en-US")
        self.assertEqual(intent.name, "test2")
        # entity values are normalized (lowercased) for matching per OVOS-INTENT-1
        self.assertEqual(intent.matches, {'thing': 'mycroft'})
        self.assertEqual(intent.sent, utterance)
        self.assertTrue(intent.conf <= 0.8)


class Intent4RegistrationTest(unittest.TestCase):
    """OVOS-INTENT-4 template registration consumed alongside legacy topics."""

    def get_service(self):
        from ovos_spec_tools import SpecMessage
        self.SpecMessage = SpecMessage
        return PadaciosoPipeline(FakeBus(), {"fuzz": False})

    def test_register_template_and_match(self):
        svc = self.get_service()
        # register a template intent via ovos.intent.register.template (§6)
        msg = Message(self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
            "skill_id": "music.skill",
            "intent_name": "play_music",
            "lang": "en-US",
            "samples": ["play {query}", "i want to listen to {query}"],
        })
        svc.handle_register_template(msg)

        # internal name is namespaced <skill_id>:<intent_name>
        self.assertIn("music.skill:play_music",
                      svc.containers["en-US"].intent_samples)

        # an utterance matches and the slot is captured
        intent = svc.calc_intent("play the beatles", "en-US")
        self.assertEqual(intent.name, "music.skill:play_music")
        self.assertEqual(intent.matches, {"query": "the beatles"})

    def test_blacklist_suppresses_match(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US", "samples": ["play {query}"],
                "blacklist": ["trailer"],
            }))
        # blacklisted phrase suppresses the match (§6.1)
        intent = svc.calc_intent("play the trailer", "en-US")
        self.assertIsNone(intent)
        # non-blacklisted utterance still matches
        intent = svc.calc_intent("play jazz", "en-US")
        self.assertEqual(intent.name, "music.skill:play_music")

    def test_entity_registration(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "music.skill", "intent_name": "play_on",
                "lang": "en-US", "samples": ["play {query} on {engine}"],
            }))
        svc.handle_register_entity(Message(
            self.SpecMessage.ENTITY_REGISTER.value, {
                "skill_id": "music.skill", "entity_name": "engine",
                "lang": "en-US", "samples": ["spotify", "youtube"],
            }))
        self.assertIn("music.skill:engine",
                      svc.containers["en-US"].entity_samples)

    def test_deregister_intent(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US", "samples": ["play {query}"],
            }))
        svc.handle_deregister_intent(Message(
            self.SpecMessage.INTENT_DEREGISTER.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US"}))
        self.assertNotIn("music.skill:play_music",
                         svc.containers["en-US"].intent_samples)
        self.assertIsNone(svc.calc_intent("play jazz", "en-US"))

    def test_deregister_skill(self):
        svc = self.get_service()
        for n in ("play_music", "stop_music"):
            svc.handle_register_template(Message(
                self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                    "skill_id": "music.skill", "intent_name": n,
                    "lang": "en-US", "samples": [f"{n} {{query}}"],
                }))
        svc.handle_deregister_skill(Message(
            self.SpecMessage.SKILL_DEREGISTER.value, {"skill_id": "music.skill"}))
        self.assertEqual(svc.containers["en-US"].intent_samples, {})

    def test_disable_then_enable(self):
        svc = self.get_service()
        reg = lambda: svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US", "samples": ["play {query}"],
            }))
        reg()
        # disable removes it from matching but keeps the definition (§8.5).
        # assert at the container level to avoid the engine's per-utterance
        # lru_cache (keyed on container+session identity) masking re-arming.
        svc.handle_disable_intent(Message(
            self.SpecMessage.INTENT_DISABLE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US"}))
        self.assertNotIn("music.skill:play_music",
                         svc.containers["en-US"].intent_samples)
        # definition retained for re-arming
        self.assertIn(("en-US", "music.skill:play_music"),
                      svc._template_samples)
        # enable re-arms it
        svc.handle_enable_intent(Message(
            self.SpecMessage.INTENT_ENABLE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US"}))
        self.assertIn("music.skill:play_music",
                      svc.containers["en-US"].intent_samples)
        intent = svc.calc_intent("play jazz", "en-US")
        self.assertEqual(intent.name, "music.skill:play_music")

    def test_disable_then_enable_legacy_registered(self):
        # §8.5 must re-arm an intent registered via the *legacy*
        # ``padatious:register_intent`` path too — that path never populates
        # ``_template_samples``, so enable relies on the samples stashed at
        # disable time. Regression for a disabled legacy intent that could
        # never be re-enabled (stayed unmatched forever).
        svc = self.get_service()
        svc.register_intent(Message("padatious:register_intent", {
            "samples": ["play {query}"], "lang": "en-US",
            "name": "music.skill:play_music"}))
        self.assertEqual(svc.calc_intent("play jazz", "en-US").name,
                         "music.skill:play_music")
        svc.handle_disable_intent(Message(
            self.SpecMessage.INTENT_DISABLE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US"}))
        self.assertNotIn("music.skill:play_music",
                         svc.containers["en-US"].intent_samples)
        svc.handle_enable_intent(Message(
            self.SpecMessage.INTENT_ENABLE.value, {
                "skill_id": "music.skill", "intent_name": "play_music",
                "lang": "en-US"}))
        self.assertIn("music.skill:play_music",
                      svc.containers["en-US"].intent_samples)
        self.assertEqual(svc.calc_intent("play jazz", "en-US").name,
                         "music.skill:play_music")

    def test_legacy_still_works(self):
        # back-compat: legacy padatious:register_intent path unchanged
        svc = self.get_service()
        svc.register_intent(Message("padatious:register_intent", {
            "samples": ["hello there"], "lang": "en-US",
            "name": "greet.skill:hello"}))
        intent = svc.calc_intent("hello there", "en-US")
        self.assertEqual(intent.name, "greet.skill:hello")


class ContextGatingTest(unittest.TestCase):
    """OVOS-CONTEXT-1 §6/§6.1 requires_context / excludes_context gating."""

    def get_service(self):
        from ovos_spec_tools import SpecMessage
        self.SpecMessage = SpecMessage
        return PadaciosoPipeline(FakeBus(), {"fuzz": False})

    def _msg_with_context(self, intent_context):
        from ovos_bus_client.session import Session
        sess = Session("test-session")
        sess.intent_context = intent_context
        return Message("recognizer_loop:utterance", {},
                       {"session": sess.serialize()})

    def test_requires_context_present_vs_absent(self):
        svc = self.get_service()
        # register an intent gated on a private context key
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "tv.skill",
                "intent_name": "turn_off",
                "lang": "en-US",
                "samples": ["turn off the tv"],
                "requires_context": ["tv_on"],
            }))
        self.assertIn(("tv.skill:turn_off"),
                      svc._intent_context_gates)

        # context absent -> gate fails -> no match
        msg = self._msg_with_context({})
        self.assertIsNone(svc.calc_intent("turn off the tv", "en-US", msg))

        # private key stored as <owner_id>:<key> -> gate satisfied -> match
        msg = self._msg_with_context({"tv.skill:tv_on": {"value": True}})
        intent = svc.calc_intent("turn off the tv", "en-US", msg)
        self.assertEqual(intent.name, "tv.skill:turn_off")

    def test_excludes_context_drops_match(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "media.skill",
                "intent_name": "play",
                "lang": "en-US",
                "samples": ["play something"],
                "excludes_context": ["playing"],
            }))
        # exclude key absent -> match allowed
        msg = self._msg_with_context({})
        self.assertEqual(
            svc.calc_intent("play something", "en-US", msg).name,
            "media.skill:play")
        # exclude key present (live) -> match dropped
        msg = self._msg_with_context({"media.skill:playing": {"value": True}})
        self.assertIsNone(svc.calc_intent("play something", "en-US", msg))

    def test_ungated_intent_unaffected(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "greet.skill",
                "intent_name": "hi",
                "lang": "en-US",
                "samples": ["hello there"],
            }))
        self.assertNotIn("greet.skill:hi", svc._intent_context_gates)
        msg = self._msg_with_context({})
        self.assertEqual(
            svc.calc_intent("hello there", "en-US", msg).name,
            "greet.skill:hi")

    def test_legacy_register_stores_gate(self):
        svc = self.get_service()
        svc.register_intent(Message("padatious:register_intent", {
            "samples": ["lock the door"], "lang": "en-US",
            "name": "home.skill:lock", "requires_context": ["armed"]}))
        self.assertIn("home.skill:lock", svc._intent_context_gates)
        self.assertIsNone(svc.calc_intent("lock the door", "en-US",
                                          self._msg_with_context({})))
        msg = self._msg_with_context({"home.skill:armed": {"value": True}})
        self.assertEqual(svc.calc_intent("lock the door", "en-US", msg).name,
                         "home.skill:lock")

    def test_gate_dropped_on_deregister(self):
        svc = self.get_service()
        svc.handle_register_template(Message(
            self.SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "tv.skill", "intent_name": "off",
                "lang": "en-US", "samples": ["off"],
                "requires_context": ["tv_on"]}))
        svc.handle_deregister_intent(Message(
            self.SpecMessage.INTENT_DEREGISTER.value, {
                "skill_id": "tv.skill", "intent_name": "off"}))
        self.assertNotIn("tv.skill:off", svc._intent_context_gates)


if __name__ == "__main__":
    unittest.main()
