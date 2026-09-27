"""OVOS-INTENT-1 §5.6 — a typed placeholder binds where the map says it may.

§5.6: "An engine **MAY** use the map to constrain where `{type:name}` matches
— preferring or requiring a span the map lists for that type". The regex
captures every word between its literals; the parser reads the datum. "set a
timer for about twenty minutes" gives the template no reason to drop the
hedge, so without the map `{number:amount}` binds "about twenty" and a skill
calling int() on it fails.

`Match.slots[name]` stays the surface string either way (PIPELINE-1 §4.3), so
the assertion is on WHICH surface is bound, never on whether a match happened.
A degrading engine matches the intent just as well and binds the wrong span.
"""
import unittest

from ovos_bus_client.message import Message
from ovos_utils.fakebus import FakeBus

from padacioso.opm import PadaciosoPipeline

LANG = "en-US"
SKILL = "timer.skill"
INTENT = "set_timer"
NAME = f"{SKILL}:{INTENT}"


def _pipeline():
    return PadaciosoPipeline(FakeBus())


def _register(pipeline, samples, slot_types=None, legacy=False):
    if legacy:
        data = {"name": f"{SKILL}:{INTENT}.intent", "lang": LANG,
                "samples": samples}
        topic = "padatious:register_intent"
    else:
        data = {"skill_id": SKILL, "intent_name": INTENT, "lang": LANG,
                "samples": samples}
        topic = "ovos.intent.register.template"
    if slot_types is not None:
        data["slot_types"] = slot_types
    pipeline.bus.emit(Message(topic, data, {"skill_id": SKILL}))


def _typed(utterance, start, end, value, type_name="number"):
    return {type_name: [{"span": [start, end],
                         "surface": utterance[start:end],
                         "value": value}]}


def _message(utterances, typed=None):
    data = {"utterances": list(utterances), "lang": LANG}
    if typed is not None:
        data["typed_slots"] = typed
    return Message("recognizer_loop:utterance", data, {})


class TestTypedSlotBinding(unittest.TestCase):
    # the template has no reason to drop "about": it binds every word
    # between "for" and "minutes"
    UTTERANCE = "set a timer for about twenty minutes"
    SAMPLES = ["set a timer for {number:amount} minutes",
               "timer {number:amount} minutes"]

    def _match(self, pipeline, utterances, typed=None, level="match_high"):
        return getattr(pipeline, level)(list(utterances), LANG,
                                        _message(utterances, typed))

    def test_the_typed_span_wins_over_the_template_guess(self):
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        start = self.UTTERANCE.index("twenty")
        typed = _typed(self.UTTERANCE, start, start + len("twenty"), 20)
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match, "the intent must still match")
        self.assertEqual(match.match_data.get("amount"), "twenty",
                         "the hedge 'about' is not part of the number")

    def test_the_legacy_topic_binds_the_typed_span_too(self):
        """The legacy ``padatious:register_intent`` payload states the types
        in the template lines only (no ``slot_types``)."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES, legacy=True)
        start = self.UTTERANCE.index("twenty")
        typed = _typed(self.UTTERANCE, start, start + len("twenty"), 20)
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "twenty")

    def test_the_payload_slot_types_win_over_the_template(self):
        """INTENT-4 §6.1: ``slot_types`` in the payload is authoritative. A
        bare ``{amount}`` typed by the payload as ``number`` binds from the
        map."""
        pipeline = _pipeline()
        _register(pipeline, ["set a timer for {amount} minutes"],
                  slot_types={"amount": "number"})
        start = self.UTTERANCE.index("twenty")
        typed = _typed(self.UTTERANCE, start, start + len("twenty"), 20)
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "twenty")

    def test_an_absent_map_leaves_the_binding_untouched(self):
        """§5.6 degrade: no map, and the typed placeholder behaves as {name}."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        match = self._match(pipeline, [self.UTTERANCE])
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty",
                         "without a typed-slot map the slot degrades to {name}")

    def test_a_malformed_map_is_ignored_rather_than_raising(self):
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        match = self._match(pipeline, [self.UTTERANCE],
                            {"number": [{"span": [0, 3]}]})
        self.assertIsNotNone(match, "a bad map must not lose the match")
        self.assertEqual(match.match_data.get("amount"), "about twenty",
                         "a malformed map leaves the template binding")

    def test_an_entry_whose_span_does_not_hold_is_not_applied(self):
        """The invariant is the selector: entries are shared across candidates
        and apply only where `utterance[start:end] == surface`."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        typed = {"number": [{"span": [0, 3], "surface": "ninety", "value": 90}]}
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty",
                         "an entry failing the invariant leaves the template binding")

    def test_an_entry_that_does_not_overlap_the_bound_is_not_applied(self):
        """No listed span overlaps the template guess: the binding stays."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        # "set" is a valid entry on this utterance, but it does not overlap
        # the template-bound "about twenty".
        typed = {"number": [{"span": [0, 3], "surface": "set", "value": 1}]}
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty",
                         "a non-overlapping entry must not replace the template binding")

    def test_two_slots_of_the_same_type_do_not_collapse(self):
        """Each entry may be assigned to at most one slot of its type."""
        pipeline = _pipeline()
        samples = ["wake me in {number:a} minutes and again in {number:b} minutes"]
        _register(pipeline, samples)
        utterance = "wake me in twenty minutes and again in ten minutes"
        # Only one number is listed in the map; the second slot must keep its
        # own template binding.
        start = utterance.index("twenty")
        typed = _typed(utterance, start, start + len("twenty"), 20)
        # two wildcard slots score 0.92 in padacioso: the medium level
        match = self._match(pipeline, [utterance], typed, level="match_medium")
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("a"), "twenty")
        self.assertEqual(match.match_data.get("b"), "ten",
                         "the only listed number must not be reused for b")

    def test_capitalized_utterance_uses_typed_span(self):
        """The invariant is checked on the original casing of the utterance."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        utterance = "Set a timer for About Twenty minutes"
        start = utterance.index("Twenty")
        typed = _typed(utterance, start, start + len("Twenty"), 20)
        match = self._match(pipeline, [utterance], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "Twenty",
                         "the typed span on capitalized input must win")

    def test_an_entry_from_another_candidate_is_not_applied(self):
        """§5.6: the map is shared by every candidate, and an entry applies
        only to the candidate the engine matched. Here the entry holds on
        candidate 0, but candidate 1 wins the match."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        noisy = "um so anyway set a timer for ninety nine minutes or so please"
        clean = "set a timer for ninety minutes"
        start = noisy.index("ninety nine")
        typed = _typed(noisy, start, start + len("ninety nine"), 99)
        match = self._match(pipeline, [noisy, clean], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.utterance, clean,
                         "control: the clean candidate must win the match")
        self.assertEqual(match.match_data.get("amount"), "ninety",
                         "an entry of another candidate must not bind")

    def test_an_unregistered_type_degrades(self):
        """`{bogus:amount}` names no registered type: nothing to bind from."""
        pipeline = _pipeline()
        _register(pipeline, ["set a timer for {bogus:amount} minutes"])
        self.assertIsNone(pipeline._intent_slot_types.get((LANG, NAME)))
        start = self.UTTERANCE.index("twenty")
        typed = {"bogus": [{"span": [start, start + 6], "surface": "twenty",
                            "value": 20}]}
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty")

    def test_detach_drops_the_declared_types(self):
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        self.assertEqual(pipeline._intent_slot_types.get((LANG, NAME)),
                         {"amount": "number"})
        pipeline.bus.emit(Message("ovos.intent.deregister",
                                  {"skill_id": SKILL, "intent_name": INTENT},
                                  {"skill_id": SKILL}))
        self.assertIsNone(pipeline._intent_slot_types.get((LANG, NAME)))


class TestClosestTypedEntry(unittest.TestCase):
    """Offsets are code points of the original utterance (§5.6 `span`)."""

    def test_a_length_changing_lowercase_keeps_offsets(self):
        from padacioso.opm import _closest_typed_entry
        # U+0130 lowercases to two code points, which shifts every offset
        # after it in the lowered string.
        utterance = "İİİİİİ ten twenty"
        self.assertNotEqual(len(utterance), len(utterance.lower()),
                            "control: the lowercase must change the length")
        ten = {"span": [7, 10], "surface": "ten", "value": 10}
        twenty = {"span": [11, 17], "surface": "twenty", "value": 20}
        self.assertIs(_closest_typed_entry([ten, twenty], utterance, "ten"), ten)
        self.assertIs(_closest_typed_entry([ten, twenty], utterance, "twenty"),
                      twenty)
