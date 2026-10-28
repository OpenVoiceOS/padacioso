"""OVOS-INTENT-2 §4.5: an intent none of whose required keywords occurs in
the utterance is suppressed, whatever its score. A keyword occurs the way a
blacklist phrase does (§4.3): as a contiguous sequence of whole words.
The keywords arrive as ``required_keywords`` on the template registration
(OVOS-INTENT-4 §6.1) and on its legacy ``padatious:register_intent`` twin.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso import IntentContainer
from padacioso.opm import PadaciosoPipeline

SAMPLES = ["how do i {query}", "search {query}"]
REQUIRED = ["wikihow", "wiki how"]
# the sibling sorts after the required intent, so an exact tie between the
# two goes to the required intent unless the requirement removes it
WIKIHOW = "skill.a:wikihow"
HOWTO = "skill.b:howto"
LANG = "en-US"


def container_match(utterance, required=REQUIRED, sibling=False):
    container = IntentContainer(n_workers=1)
    container.add_intent(WIKIHOW, SAMPLES)
    if required is not None:
        container.require_keywords(WIKIHOW, required)
    if sibling:
        container.add_intent(HOWTO, ["how do i {query}"])
    return container.calc_intent(utterance)["name"]


class TestContainerRequiredKeywords(unittest.TestCase):
    def test_a_required_keyword_lets_the_intent_match(self):
        self.assertEqual(container_match("how do i tie a tie on wikihow"),
                         WIKIHOW)

    def test_no_required_keyword_suppresses_the_intent(self):
        self.assertIsNone(container_match("how do i tie a tie"))

    def test_a_multi_word_keyword_occurs_as_a_word_sequence(self):
        self.assertEqual(container_match("search wiki how for knots"), WIKIHOW)

    def test_a_keyword_inside_a_longer_word_does_not_occur(self):
        self.assertIsNone(container_match("how do i tie a tie on wikihowto"))
        self.assertIsNone(container_match("search wiki howto for knots"))

    def test_keywords_fold_like_the_utterance(self):
        self.assertEqual(container_match("how do i tie a tie on WikiHow"),
                         WIKIHOW)
        self.assertEqual(
            container_match("how do i tie a tie on wikihow",
                            required=["WIKIHÓW"]), WIKIHOW)

    def test_an_intent_without_required_keywords_is_unaffected(self):
        self.assertEqual(container_match("how do i tie a tie", required=None),
                         WIKIHOW)

    def test_a_sibling_intent_is_unaffected(self):
        self.assertEqual(container_match("how do i tie a tie", sibling=True),
                         HOWTO)

    def test_keywords_that_fold_to_nothing_add_no_requirement(self):
        self.assertEqual(container_match("how do i tie a tie", required=["?!"]),
                         WIKIHOW)

    def test_registered_list_is_not_mutated(self):
        keywords = ["WikiHow"]
        IntentContainer().require_keywords(WIKIHOW, keywords)
        self.assertEqual(keywords, ["WikiHow"])


def template_msg(intent_name, samples, **extra):
    skill_id, name = intent_name.split(":")
    return Message("ovos.intent.register.template", {
        "skill_id": skill_id, "intent_name": name, "lang": LANG,
        "samples": samples, **extra}, {"skill_id": skill_id})


def legacy_msg(intent_name, samples, **extra):
    skill_id = intent_name.split(":")[0]
    return Message("padatious:register_intent", {
        "skill_id": skill_id, "name": f"{intent_name}.intent", "lang": LANG,
        "samples": samples, **extra}, {"skill_id": skill_id})


class TestPipelineRequiredKeywords(unittest.TestCase):
    def setUp(self):
        self.pipeline = PadaciosoPipeline(FakeBus())
        self.pipeline.containers.setdefault(LANG, IntentContainer(n_workers=1))

    def matched(self, utterance):
        intent = self.pipeline.calc_intent([utterance], lang=LANG)
        return intent.name if intent else None

    def assert_required(self):
        self.assertEqual(self.matched("how do i tie a tie on wikihow"), WIKIHOW)
        self.assertEqual(self.matched("search wiki how for knots"), WIKIHOW)
        self.assertIsNone(self.matched("how do i tie a tie"))
        self.assertIsNone(self.matched("how do i tie a tie on wikihowto"))

    def test_template_registration(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.assert_required()

    def test_legacy_registration(self):
        self.pipeline.register_intent(
            legacy_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.assert_required()

    def test_template_then_legacy_registration(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.pipeline.register_intent(
            legacy_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.assert_required()

    def test_legacy_then_template_registration(self):
        self.pipeline.register_intent(
            legacy_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.assert_required()

    def test_a_sibling_intent_is_unaffected(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.pipeline.handle_register_template(
            template_msg(HOWTO, ["how do i {query}"]))
        self.assertEqual(self.matched("how do i tie a tie"), HOWTO)
        self.assertEqual(self.matched("search wiki how for knots"), WIKIHOW)

    def test_an_intent_without_required_keywords_is_unaffected(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=[]))
        self.assertEqual(self.matched("how do i tie a tie"), WIKIHOW)

    def test_re_registration_replaces_the_keywords(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=["kongzi"]))
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.assert_required()
        self.assertIsNone(self.matched("how do i greet kongzi"))

    def test_template_re_registration_without_keywords_drops_them(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.pipeline.handle_register_template(template_msg(WIKIHOW, SAMPLES))
        self.assertEqual(self.matched("how do i tie a tie"), WIKIHOW)

    def test_legacy_re_registration_without_keywords_drops_them(self):
        self.pipeline.register_intent(
            legacy_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        self.pipeline.register_intent(legacy_msg(WIKIHOW, SAMPLES))
        self.assertEqual(self.matched("how do i tie a tie"), WIKIHOW)

    def test_disable_and_enable_keep_the_requirement(self):
        self.pipeline.handle_register_template(
            template_msg(WIKIHOW, SAMPLES, required_keywords=REQUIRED))
        target = {"skill_id": "skill.a", "intent_name": "wikihow", "lang": LANG}
        self.pipeline.handle_disable_intent(
            Message("ovos.intent.disable", target))
        self.pipeline.handle_enable_intent(
            Message("ovos.intent.enable", target))
        self.assert_required()


if __name__ == "__main__":
    unittest.main()
