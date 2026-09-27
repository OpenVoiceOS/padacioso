import unittest

from padacioso import IntentContainer


class TestSlotValueIsTheSpokenText(unittest.TestCase):
    """A captured slot carries the words the user said, not the folded form.

    OVOS-INTENT-1 §5.2: under match-time fill "the engine captures a span of
    the utterance". §5.3: "The slot itself still fills with the surface words
    the user spoke."

    Matching runs on the folded form, because a template and an utterance must
    compare consistently. The captured VALUE is a different question. While
    the query was folded in place, an open-text slot handed the skill
    ``rod`` for a spoken ``röd``, and a Swedish speaker asking for red was
    told the colour does not exist (measured end to end on
    ovos-skill-color-picker#66).

    ``rød`` is the control: o-slash is a letter in its own right, not o plus a
    combining mark, so it never folded and never showed the defect. A fix that
    only repaired ``rød`` would prove nothing.
    """

    def setUp(self):
        self.container = IntentContainer()
        self.container.add_intent("color", ["visa mig färgen {color}",
                                            "show me the color {color}"])

    def _color(self, utterance):
        match = self.container.calc_intent(utterance)
        self.assertIsNotNone(match, f"{utterance!r} did not match at all")
        return match["entities"].get("color")

    def test_a_combining_mark_survives_into_the_slot(self):
        self.assertEqual(self._color("visa mig färgen röd"), "röd")
        self.assertEqual(self._color("visa mig färgen grön"), "grön")
        self.assertEqual(self._color("show me the color café"), "café")

    def test_a_letter_that_never_folded_still_works(self):
        """The control. o-slash is its own letter, so it never stripped."""
        self.assertEqual(self._color("visa mig färgen rød"), "rød")

    def test_an_ascii_value_is_unchanged(self):
        self.assertEqual(self._color("show me the color red"), "red")
        self.assertEqual(self._color("visa mig färgen blue"), "blue")

    def test_routing_is_unaffected(self):
        """The defect was the value, never the match; it must stay that way."""
        match = self.container.calc_intent("visa mig färgen röd")
        self.assertEqual(match["name"], "color")
        self.assertGreater(match["conf"], 0.9)

    def test_a_multi_word_slot_keeps_every_surface_word(self):
        container = IntentContainer()
        container.add_intent("play", ["spela {song}"])
        match = container.calc_intent("spela härlig är jorden")
        self.assertEqual(match["entities"]["song"], "härlig är jorden")

    def test_a_token_that_folds_away_does_not_shift_the_span(self):
        """Bare punctuation drops from the folded and the surface list alike,
        so the two stay aligned and the slot is still the right word."""
        container = IntentContainer()
        container.add_intent("color", ["färgen {color} tack"])
        match = container.calc_intent("färgen röd ! tack")
        self.assertIsNotNone(match)
        self.assertEqual(match["entities"]["color"], "röd")

    def test_two_slots_that_fold_alike_each_get_their_own_words(self):
        """``röd`` and ``rod`` both fold to ``rod``. Each slot must report the
        word at its own position, so the span search walks forward."""
        container = IntentContainer()
        container.add_intent("two", ["{a} och {b}"])
        for utterance, first, second in (("röd och rod", "röd", "rod"),
                                         ("rod och röd", "rod", "röd"),
                                         ("grön och gron", "grön", "gron")):
            with self.subTest(utterance=utterance):
                entities = container.calc_intent(utterance)["entities"]
                self.assertEqual(entities["a"], first)
                self.assertEqual(entities["b"], second)

    def test_a_wildcard_pattern_still_fills_its_slot(self):
        container = IntentContainer()
        container.add_intent("say", ["säg * till {who}"])
        match = container.calc_intent("säg hej till mögel")
        self.assertEqual(match["entities"]["who"], "mögel")

    def test_a_registered_entity_value_reads_back_spoken(self):
        container = IntentContainer()
        container.add_intent("pick", ["välj {color}"])
        container.add_entity("color", ["röd", "grön"])
        match = container.calc_intent("välj röd")
        self.assertEqual(match["entities"]["color"], "röd")


class TestMatchNormalizationIsUnchanged(unittest.TestCase):
    """The folding itself is untouched: only the reported value changed."""

    def test_a_template_without_diacritics_matches_a_spoken_one(self):
        """Why the match keeps folding: the two sides must still meet."""
        container = IntentContainer()
        container.add_intent("color", ["visa mig fargen {color}"])
        match = container.calc_intent("visa mig färgen röd")
        self.assertIsNotNone(match, "the folded forms must still match")
        self.assertEqual(match["entities"]["color"], "röd")

    def test_normalize_still_folds(self):
        from padacioso import _normalize
        self.assertEqual(_normalize("Visa MIG färgen"), "visa mig fargen")
        self.assertEqual(_normalize("a  b"), "a b")


if __name__ == "__main__":
    unittest.main()
class TestSlotValueKeepsItsCase(unittest.TestCase):
    """A name the user capitalised reaches the skill capitalised.

    T-5676: an alert named ``Åsa`` was stored and spoken as ``asa``. Two losses
    stacked, and the diacritic was only the first. OVOS-INTENT-1 §2 asks an
    upstream stage to lowercase an utterance before it reaches an engine, and in
    the fleet it does not: ``lösche meinen Alarm für Zahnarzt`` arrives with its
    capital. §5.2 says the engine captures a span of the utterance and §5.3 that
    the slot fills with the surface words the user spoke, so folding the case
    here destroyed a name the user gave.

    A consumer that wants a folded form can fold what it is handed. A consumer
    handed the folded form cannot get the original back.
    """

    #: the lines localize measured, one per locale, each with a diacritic and a
    #: capital in the name
    CASES = (
        ("sv-SE", "avbryt mitt larm för {name}", "avbryt mitt larm för Åsa",
         "Åsa"),
        ("de-DE", "lösche meinen Alarm für {name}",
         "lösche meinen Alarm für Zahnarzt", "Zahnarzt"),
        ("ca-ES", "cancel·la la meva alarma per {name}",
         "cancel·la la meva alarma per Núria", "Núria"),
    )

    def _name(self, template, utterance):
        container = IntentContainer()
        container.add_intent("cancel_alert", [template])
        match = container.calc_intent(utterance)
        self.assertIsNotNone(match, f"{utterance!r} did not match")
        return match["entities"].get("name")

    def test_the_name_survives_in_every_measured_locale(self):
        for lang, template, utterance, spoken in self.CASES:
            with self.subTest(lang=lang):
                self.assertEqual(self._name(template, utterance), spoken)

    def test_a_lowercase_name_is_unchanged(self):
        """The control: nothing is capitalised that the user did not."""
        self.assertEqual(
            self._name("avbryt mitt larm för {name}",
                       "avbryt mitt larm för tandläkare"), "tandläkare")

    def test_the_match_still_ignores_case(self):
        """Case is kept in the VALUE and still folded for the MATCH, so a
        template written lowercase matches an utterance that is not."""
        container = IntentContainer()
        container.add_intent("cancel_alert", ["avbryt mitt larm for {name}"])
        match = container.calc_intent("Avbryt Mitt Larm För Åsa")
        self.assertIsNotNone(match, "the folded forms must still meet")
        self.assertEqual(match["entities"]["name"], "Åsa")

    def test_a_multi_word_name_keeps_every_capital(self):
        self.assertEqual(
            self._name("avbryt mitt larm för {name}",
                       "avbryt mitt larm för Åsa Öberg"), "Åsa Öberg")
