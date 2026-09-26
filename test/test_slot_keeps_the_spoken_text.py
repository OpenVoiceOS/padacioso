"""A slot value is the span of the utterance it was read from.

T-5569. Matching runs on the folded query — `ovos_spec_tools.normalize_for_match`
lowercases and strips combining marks, and `_normalize` applies it to every
token before a pattern is tried. That is what §2 normalization is for. What
the skill is handed is a different question, and OVOS-INTENT-1 §5.6 answers
it:

    `Match.slots[name]` remains the **surface string** in every case
    (OVOS-PIPELINE-1 §4.3)

with the surface tied to the utterance in the same section:

    `span` and `surface` are tied by one invariant: `utterance[start:end] ==
    surface`.

OVOS-INTENT-3 §7 says the same from the other side: the slot map is "a
mapping of names to extracted text values", and slot values are "opaque
sequences of words, returned as text".

A folded `'rod'` is no span of `'visa mig färgen röd'`, so a slot carrying it
satisfies neither clause. Measured end to end on ovos-skill-color-picker#66:
the Swedish row routes, the skill logs `Requested color: rod`, and
`ovos_color_parser.color_from_description('rod', lang='sv')` returns None
where `('röd', lang='sv')` returns a colour.

`rød` is the control that isolates the mechanism: o-slash is a letter of its
own, not o plus a combining mark, so it survives the fold and always reached
the skill intact.
"""
import unittest

from padacioso import IntentContainer


class TestTheSlotIsWhatTheUserSaid(unittest.TestCase):

    def _container(self):
        container = IntentContainer()
        container.add_intent("color", ["visa mig färgen {color}",
                                       "vis mig farven {color}",
                                       "show me the color {color}"])
        return container

    def test_a_combining_mark_survives_into_the_slot(self):
        """The defect, as the skill sees it."""
        intent = self._container().calc_intent("visa mig färgen röd")
        self.assertEqual(intent["name"], "color")
        self.assertEqual(intent["entities"], {"color": "röd"})

    def test_the_danish_control_still_passes(self):
        """`ø` is a letter, not a combining mark, so this row passed before
        the fix as well. It is here to isolate the mechanism: if this one ever
        fails, the cause is not combining-mark folding."""
        intent = self._container().calc_intent("vis mig farven rød")
        self.assertEqual(intent["name"], "color")
        self.assertEqual(intent["entities"], {"color": "rød"})

    def test_the_rule_is_not_only_about_swedish(self):
        for utterance, value in (("show me the color café", "café"),
                                 ("show me the color grün", "grün"),
                                 ("show me the color Ångström", "Ångström")):
            with self.subTest(utterance=utterance):
                intent = self._container().calc_intent(utterance)
                self.assertEqual(intent["entities"], {"color": value})

    def test_the_case_the_user_used_survives_too(self):
        """The same clause: the surface is the text the datum was read from,
        and the fold lowercases. A consumer that wants a folded form folds it
        itself; one that wants to echo the user cannot un-fold."""
        intent = self._container().calc_intent("show me the color Deep Blue")
        self.assertEqual(intent["entities"], {"color": "Deep Blue"})

    def test_matching_still_runs_on_the_folded_form(self):
        """The control for the whole change: the fold still does its work.
        A template authored with the diacritic matches an utterance without
        it, and the other way round, because both sides are folded before the
        pattern is tried. Only the value handed back changed."""
        container = self._container()
        self.assertEqual(container.calc_intent("visa mig fargen rod")["name"],
                         "color")
        self.assertEqual(container.calc_intent("SHOW ME THE COLOR RED")["name"],
                         "color")

    def test_a_multi_word_slot_keeps_every_word(self):
        container = IntentContainer()
        container.add_intent("play", ["spela {track}"])
        intent = container.calc_intent("spela Blåa Ögon i Natten")
        self.assertEqual(intent["entities"], {"track": "Blåa Ögon i Natten"})

    def test_a_context_value_is_not_rewritten(self):
        """OVOS-CONTEXT-1 §7: a live context candidate that replaces the
        utterance-extracted value came from the session, not from the
        utterance. It is not a span of anything the user said, so the
        restoration must leave it alone rather than invent a span for it."""
        container = IntentContainer()
        container.add_intent("skill:color", ["visa mig färgen {color}"])
        container.add_entity("color", ["grön", "blå"])
        matches = list(container.calc_intents(
            "visa mig färgen röd",
            slot_context={("skill", "color"): "blå"}))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["entities"], {"color": "blå"})

    def test_an_entity_member_is_no_longer_penalised_for_its_diacritic(self):
        """A second effect of reading the surface before the membership
        check. `entity_samples` keeps what the skill declared, `röd`, and the
        folded `rod` was not a member of it, so a correct binding took the
        0.1 not-in-samples penalty. The two confidences are compared rather
        than pinned, so this does not fix the penalty's size."""
        with_entity = IntentContainer()
        with_entity.add_intent("color", ["visa mig färgen {color}"])
        with_entity.add_entity("color", ["röd", "grön"])
        member = with_entity.calc_intent("visa mig färgen röd")

        stranger = with_entity.calc_intent("visa mig färgen magenta")
        self.assertEqual(member["entities"], {"color": "röd"})
        self.assertGreater(member["conf"], stranger["conf"])


if __name__ == "__main__":
    unittest.main()
