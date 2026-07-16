"""Regression tests for the ``mycroft.skills.train`` acknowledgement.

ovos-core requests pipeline training at boot with
``wait_for_response(Message("mycroft.skills.train"), "mycroft.skills.trained")``.
Padacioso compiles intents at registration time, so it must answer
immediately; otherwise installs without an engine that has a real training
step wait out the full training timeout and log a misleading error.
"""

import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline


class TestTrainAck(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.pipeline = PadaciosoPipeline(self.bus, {})
        self.trained = []
        self.bus.on("mycroft.skills.trained", self.trained.append)

    def test_acks_train_request(self):
        self.bus.emit(Message("mycroft.skills.train"))
        self.assertEqual(len(self.trained), 1)
        self.assertEqual(self.trained[0].msg_type, "mycroft.skills.trained")

    def test_ack_preserves_message_context(self):
        self.bus.emit(Message("mycroft.skills.train",
                              context={"session": {"session_id": "abc"}}))
        self.assertEqual(
            self.trained[0].context.get("session", {}).get("session_id"),
            "abc")

    def test_no_ack_after_shutdown(self):
        self.pipeline.shutdown()
        self.bus.emit(Message("mycroft.skills.train"))
        self.assertEqual(self.trained, [])


if __name__ == "__main__":
    unittest.main()
