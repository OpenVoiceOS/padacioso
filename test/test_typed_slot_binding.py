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

    def test_a_typed_slot_that_binds_no_listed_span_does_not_match(self):
        """§5.6 "requiring a span the map lists for that type": the map places
        the only number at "set", so the template guess "about twenty" holds
        no number and the template does not match."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        typed = {"number": [{"span": [0, 3], "surface": "set", "value": 1}]}
        self.assertIsNone(self._match(pipeline, [self.UTTERANCE], typed),
                          "a typed slot must not bind words the map lists no value in")

    def test_a_type_the_map_does_not_list_leaves_the_slot_to_the_template(self):
        """The transformer omits a type that produced nothing, and also one
        whose parser lacks the language, so a map without numbers says
        nothing about "about twenty"."""
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        typed = {"date": [{"span": [0, 3], "surface": "set", "value": "2030-01-01"}]}
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty")

    def test_two_slots_of_the_same_type_do_not_collapse(self):
        """Each entry may be assigned to at most one slot of its type."""
        pipeline = _pipeline()
        samples = ["wake me in {number:a} minutes and again in {number:b} minutes"]
        _register(pipeline, samples)
        utterance = "wake me in twenty minutes and again in ten minutes"
        # both slots overlap only their own entry, and each entry is used once
        twenty, ten = utterance.index("twenty"), utterance.index("ten ")
        typed = {"number": [
            {"span": [ten, ten + 3], "surface": "ten", "value": 10},
            {"span": [twenty, twenty + 6], "surface": "twenty", "value": 20}]}
        # two wildcard slots score 0.92 in padacioso: the medium level
        match = self._match(pipeline, [utterance], typed, level="match_medium")
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("a"), "twenty")
        self.assertEqual(match.match_data.get("b"), "ten",
                         "each slot binds its own listed number")

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
        self.assertIsNone(pipeline.containers[LANG].slot_types.get(NAME))
        start = self.UTTERANCE.index("twenty")
        typed = {"bogus": [{"span": [start, start + 6], "surface": "twenty",
                            "value": 20}]}
        match = self._match(pipeline, [self.UTTERANCE], typed)
        self.assertIsNotNone(match)
        self.assertEqual(match.match_data.get("amount"), "about twenty")

    def test_detach_drops_the_declared_types(self):
        pipeline = _pipeline()
        _register(pipeline, self.SAMPLES)
        self.assertEqual(pipeline.containers[LANG].slot_types.get(NAME),
                         {"amount": "number"})
        pipeline.bus.emit(Message("ovos.intent.deregister",
                                  {"skill_id": SKILL, "intent_name": INTENT},
                                  {"skill_id": SKILL}))
        self.assertIsNone(pipeline.containers[LANG].slot_types.get(NAME))


class TestDateSlotRejectsNonDates(unittest.TestCase):
    """A ``{date:time}`` slot never binds "play jazz".

    The alerts skill ships both intents below. Without the typed-slot map
    requirement, reschedule_alert binds ``time="play jazz"`` and outscores
    change_media_properties, whose ``schedkind`` is no member of its entity.
    """
    SKILL = "alerts.skill"
    UTTERANCE = "change my 7 am alarm to play jazz"

    def setUp(self):
        self.pipeline = _pipeline()
        for intent, samples in (
                ("reschedule_alert", ["change my {date:old} alarm to {date:time}"]),
                ("change_media_properties", ["change my {schedkind} to play {mediakind}"])):
            self.pipeline.bus.emit(Message(
                "ovos.intent.register.template",
                {"skill_id": self.SKILL, "intent_name": intent, "lang": LANG,
                 "samples": samples}, {"skill_id": self.SKILL}))
        self.pipeline.bus.emit(Message(
            "ovos.entity.register",
            {"skill_id": self.SKILL, "entity_name": "schedkind", "lang": LANG,
             "samples": ["alarm"]}, {"skill_id": self.SKILL}))

    def _match(self, utterance, dates):
        typed = {"date": [{"span": [utterance.index(d), utterance.index(d) + len(d)],
                           "surface": d, "value": value} for d, value in dates.items()]}
        return self.pipeline.match_low([utterance], LANG, _message([utterance], typed))

    def test_words_that_hold_no_date_are_not_a_time(self):
        match = self._match(self.UTTERANCE, {"7 am": "2030-01-01T07:00:00+00:00"})
        self.assertIsNotNone(match)
        self.assertEqual(match.match_type, f"{self.SKILL}:change_media_properties")
        self.assertEqual(match.match_data.get("mediakind"), "jazz")

    def test_a_listed_date_is_a_time(self):
        utterance = "change my 7 am alarm to 8 am"
        match = self._match(utterance, {"7 am": "2030-01-01T07:00:00+00:00",
                                        "8 am": "2030-01-01T08:00:00+00:00"})
        self.assertIsNotNone(match)
        self.assertEqual(match.match_type, f"{self.SKILL}:reschedule_alert")
        self.assertEqual(match.match_data.get("time"), "8 am")


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


class TestFuzzyMatchRequiresTheTypedSpan(unittest.TestCase):
    """The fuzzy pass holds a typed slot to the same rule as the exact pass."""

    def _calc(self, utterance, dates):
        from padacioso import IntentContainer
        container = IntentContainer(fuzz=True)
        container.add_intent("alerts.skill:reschedule_alert",
                             ["change my {old} alarm to {time}"])
        container.slot_types["alerts.skill:reschedule_alert"] = {"old": "date", "time": "date"}
        spans = frozenset(("date", utterance.index(d), utterance.index(d) + len(d))
                          for d in dates)
        return list(container.calc_intents(utterance, typed_spans=spans))

    def test_a_fuzzy_candidate_binding_no_date_is_rejected(self):
        # "please" makes the exact pass miss, so only the fuzzy pass can match
        self.assertEqual(self._calc("please change my 7 am alarm to play jazz", ["7 am"]), [])

    def test_a_fuzzy_candidate_binding_listed_dates_matches(self):
        matches = self._calc("please change my 7 am alarm to 8 am", ["7 am", "8 am"])
        self.assertEqual([m["name"] for m in matches], ["alerts.skill:reschedule_alert"])
        self.assertEqual(matches[0]["entities"]["time"], "8 am")
