from padacioso import IntentContainer
from padacioso.opm import PadaciosoPipeline
from ovos_bus_client.message import Message
from ovos_spec_tools import SpecMessage
from ovos_utils.messagebus import FakeBus
import unittest


class TestTieBreakSpecificity(unittest.TestCase):
    """Regression for score ties broken by pattern specificity, not by the
    intent name string. Two patterns with a single unregistered slot each
    tie on confidence; the one with more literal tokens (i.e. a smaller
    share of the utterance captured by slots) must win.
    """

    def test_more_specific_pattern_wins_over_alphabetically_earlier_name(self):
        container = IntentContainer()
        container.add_intent('request-color', ["what colour is {requested_color}"])
        container.add_intent('request-color-by-rgb', ["what colour is the rgb value {rgb}"])

        self.assertEqual(
            container.calc_intent("what colour is the rgb value 128 128 128")['name'],
            'request-color-by-rgb'
        )
        self.assertEqual(
            container.calc_intent("what colour is teal")['name'],
            'request-color'
        )

    def test_specificity_wins_regardless_of_registration_order_or_name(self):
        # the more literal pattern is registered under the alphabetically
        # LATER name, and must still win the tie
        container = IntentContainer()
        container.add_intent('zzz-generic', ["what colour is {requested_color}"])
        container.add_intent('aaa-specific', ["what colour is the rgb value {rgb}"])

        self.assertEqual(
            container.calc_intent("what colour is the rgb value 128 128 128")['name'],
            'aaa-specific'
        )


class TestOpmTieBreakSpecificity(unittest.TestCase):
    """The pipeline-level match in opm.py's ``_calc_padacioso_intent`` must
    resolve ties with the same specificity rule as ``IntentContainer.
    calc_intent``, not its own separate ``ties[0]`` fallback.
    """

    def test_more_specific_pattern_wins_over_alphabetically_earlier_name(self):
        svc = PadaciosoPipeline(FakeBus(), {"fuzz": False})
        svc.handle_register_template(Message(
            SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "color.skill", "intent_name": "request-color",
                "lang": "en-US", "samples": ["what colour is {requested_color}"],
            }))
        svc.handle_register_template(Message(
            SpecMessage.INTENT_REGISTER_TEMPLATE.value, {
                "skill_id": "color.skill", "intent_name": "request-color-by-rgb",
                "lang": "en-US",
                "samples": ["what colour is the rgb value {rgb}"],
            }))

        intent = svc.calc_intent("what colour is the rgb value 128 128 128", "en-US")
        self.assertEqual(intent.name, "color.skill:request-color-by-rgb")

        intent = svc.calc_intent("what colour is teal", "en-US")
        self.assertEqual(intent.name, "color.skill:request-color")


if __name__ == '__main__':
    unittest.main()
