from padacioso import IntentContainer
import unittest


class TestIntentContainer(unittest.TestCase):
    # test intent syntax (OVOS-INTENT-1 grammar: [optional], (a|b), {slot})
    def test_one_of(self):
        container = IntentContainer()
        container.add_intent('hello', ["(hello|hi|hey) world"])
        self.assertEqual(sorted(container.intent_samples["hello"]),
                         sorted(['hello world', 'hi world', 'hey world']))

    def test_optionally(self):
        container = IntentContainer()
        container.add_intent('hello', ["hello (world|)"])
        self.assertEqual(sorted(container.intent_samples["hello"]),
                         sorted(['hello world', 'hello']))

        container.add_intent('hey', ["hey [world]"])
        self.assertEqual(sorted(container.intent_samples["hey"]),
                         sorted(['hey world', 'hey']))

        container.add_intent('hi', ["hi [{person}|people]"])
        self.assertEqual(sorted(container.intent_samples["hi"]),
                         sorted(['hi {person}', 'hi people', 'hi']))

    # test intent parsing
    def test_intents(self):
        container = IntentContainer()
        container.add_intent('hello', [
            'hello', 'hi', 'how are you', "what's up"
        ])
        container.add_intent('buy', [
            'buy {item}', 'purchase {item}', 'get {item}', 'get {item} for me'
        ])
        container.add_entity('item', [
            'milk', 'cheese'
        ])
        container.add_intent('drive', [
            'drive me to {place}', 'take me to {place}', 'navigate to {place}'
        ])
        container.add_intent('eat', [
            'eat {fruit}', 'eat some {fruit}', 'munch on (some|) {fruit}'
        ])
        self.assertEqual(container.calc_intent('hello')['name'], 'hello')
        self.assertEqual(container.calc_intent('bye')['name'], None)
        self.assertEqual(container.calc_intent('buy milk'), {
            'name': 'buy', 'entities': {'item': 'milk'},  "conf": 1
        })
        self.assertEqual(container.calc_intent('buy beer'), {
            'name': 'buy', 'entities': {'item': 'beer'},
            "conf": 0.9  # unseen entity example
        })
        self.assertEqual(container.calc_intent('eat some bananas'), {
            'name': 'eat', 'entities': {'fruit': 'bananas'},
            "conf": 0.96  # unregistered entity
        })
        self.assertEqual(container.calc_intent("drive me to the store"), {
            'name': 'drive', 'entities': {'place': 'the store'},
            'conf': 0.96
        })

    def test_multiple_entities(self):
        container = IntentContainer()
        container.add_intent('test3', ['I see {thing} (in|on) {place}'])
        self.assertEqual(
            container.calc_intent('I see a bin in there'),
            {'conf': 0.92,  # unregistered entity * 2
             'entities': {'place': 'there', 'thing': 'a bin'},
             'name': 'test3'}
        )

    def test_wildcards(self):
        container = IntentContainer()
        container.add_intent('test', ['say *'])
        self.assertEqual(
            container.calc_intent('say something, whatever'),
            {'conf': 0.85,  # wildcard
             'entities': {}, 'name': 'test'})

    def test_no_fuzz(self):
        container = IntentContainer(fuzz=False)
        container.add_intent('test', ['this is a test',
                                      'test the intent',
                                      'execute test'])
        container.add_intent('test2', ['tell me about {thing}',
                                       'what is {thing}'])
        # exact match
        intent = container.calc_intent("this is a test")
        self.assertEqual(intent["name"], "test")

        # regex match (entity value is normalized for matching)
        intent = container.calc_intent("tell me about Mycroft")
        self.assertEqual(intent["name"], "test2")
        self.assertEqual(intent["entities"], {'thing': 'mycroft'})

        # fuzzy match - failure case (no fuzz)
        intent = container.calc_intent("this is test")
        self.assertTrue(intent["name"] is None)

        # fuzzy regex match - failure case (no fuzz)
        intent = container.calc_intent("tell me everything about Mycroft")
        self.assertTrue(intent["name"] is None)

    def test_fuzz(self):
        container = IntentContainer(fuzz=True)
        container.add_intent('test', ['this is a test',
                                      'test the intent',
                                      'execute test'])
        container.add_intent('test2', ['tell me about {thing}',
                                       'what is {thing}'])
        # exact match
        intent = container.calc_intent("this is a test")
        self.assertEqual(intent["name"], "test")

        # regex match
        intent = container.calc_intent("tell me about Mycroft")
        self.assertEqual(intent["name"], "test2")
        self.assertEqual(intent["entities"], {'thing': 'mycroft'})

        # fuzzy match
        intent = container.calc_intent("this is test")
        self.assertEqual(intent["name"], "test")

        # fuzzy regex match
        intent = container.calc_intent("tell me everything about Mycroft")
        self.assertEqual(intent["name"], "test2")
        self.assertEqual(intent["entities"], {'thing': 'mycroft'})

    def test_add_remove_intent(self):
        container = IntentContainer()
        # Add intent valid
        container.add_intent("hello", ["hi", "hello", "howdy",
                                       "how (are you|do you do)"])
        self.assertEqual(len(container.intent_samples['hello']), 5)
        self.assertEqual(len(container._cased_matchers), 5)
        self.assertEqual(len(container._cased_matchers),
                         len(container._uncased_matchers))
        # Add intent already defined
        with self.assertRaises(RuntimeError):
            container.add_intent("hello", ["invalid"])
        # Add second intent
        container.add_intent("test", ["test(ing|)"])
        self.assertEqual(len(container.intent_samples['test']), 2)
        self.assertEqual(len(container._cased_matchers),
                         len(container._uncased_matchers))
        # Remove intent
        container.remove_intent("test")
        self.assertNotIn("test", container.intent_samples)
        self.assertEqual(len(container.intent_samples['hello']), 5)
        self.assertEqual(len(container._cased_matchers), 5)
        self.assertEqual(len(container._cased_matchers),
                         len(container._uncased_matchers))

    def test_add_remove_entity(self):
        container = IntentContainer()
        # Add entity valid
        container.add_entity("entity", ["test(ing|)", "another test"])
        self.assertEqual(len(container.entity_samples["entity"]), 3)
        # Add entity already defined
        with self.assertRaises(RuntimeError):
            container.add_entity("entity", ["invalid"])
        # Remove entity
        container.remove_entity("entity")
        self.assertNotIn("entity", container.entity_samples.keys())

    # normalization integration tests (delegated to ovos-spec-tools)
    def test_double_whitespace_in_query(self):
        """Extra whitespace in the spoken query should not prevent matching."""
        container = IntentContainer()
        container.add_intent('hello', ['hello world'])
        self.assertEqual(container.calc_intent('hello  world')['name'], 'hello')
        self.assertEqual(container.calc_intent('  hello world  ')['name'], 'hello')
        self.assertEqual(container.calc_intent('hello   world')['name'], 'hello')

    def test_double_whitespace_in_training(self):
        """Extra whitespace in training data is collapsed at registration time
        by ovos_spec_tools.expand, so a double-spaced sample matches a
        single-spaced utterance."""
        container = IntentContainer()
        container.add_intent('count', ['count forever  using short scale'])
        self.assertIn('count forever using short scale',
                      container.intent_samples['count'])
        self.assertNotIn('count forever  using short scale',
                         container.intent_samples['count'])
        self.assertEqual(
            container.calc_intent('count forever using short scale')['name'],
            'count')

    def test_whitespace_with_entity(self):
        """Whitespace normalization should not corrupt extracted entity values."""
        container = IntentContainer()
        container.add_intent('buy', ['buy {item}'])
        match = container.calc_intent('buy   milk')
        self.assertEqual(match['name'], 'buy')
        self.assertEqual(match['entities']['item'], 'milk')

    def test_leading_trailing_whitespace_query(self):
        """Leading/trailing whitespace on the query should be stripped."""
        container = IntentContainer()
        container.add_intent('hello', ['hello'])
        self.assertEqual(container.calc_intent('  hello  ')['name'], 'hello')


class TestExpand(unittest.TestCase):
    """Template expansion is delegated to ovos_spec_tools.expand; these tests
    exercise the spec-compliant grammar through IntentContainer registration."""

    def _samples(self, template):
        container = IntentContainer()
        container.add_intent('x', [template])
        return sorted(container.intent_samples['x'])

    # --- no-op cases ---

    def test_plain_string(self):
        self.assertEqual(self._samples("hello world"), ["hello world"])

    def test_entity_placeholder_untouched(self):
        # {entity} must survive expansion unchanged
        self.assertEqual(self._samples("buy {item}"), ["buy {item}"])

    # --- (a|b) alternatives ---

    def test_two_alternatives(self):
        self.assertEqual(self._samples("(hello|hi)"), sorted(["hello", "hi"]))

    def test_three_alternatives(self):
        self.assertEqual(self._samples("(hello|hi|hey) world"),
                         sorted(["hello world", "hey world", "hi world"]))

    def test_alternatives_at_end(self):
        self.assertEqual(self._samples("turn (on|off)"),
                         sorted(["turn off", "turn on"]))

    def test_two_independent_groups(self):
        self.assertEqual(self._samples("(a|b) (c|d)"),
                         sorted(["a c", "a d", "b c", "b d"]))

    def test_empty_alternative_makes_optional(self):
        # (word|) is the canonical optional form
        self.assertEqual(self._samples("hello (world|)"),
                         sorted(["hello", "hello world"]))

    # --- [optional] syntax ---

    def test_optional_word(self):
        self.assertEqual(self._samples("hey [world]"),
                         sorted(["hey", "hey world"]))

    def test_optional_at_start(self):
        self.assertEqual(self._samples("[please] turn on"),
                         sorted(["please turn on", "turn on"]))

    def test_optional_entity_placeholder(self):
        self.assertEqual(self._samples("hi [{person}|people]"),
                         sorted(["hi", "hi {person}", "hi people"]))

    # --- nested / combined ---

    def test_alternatives_inside_optional(self):
        self.assertEqual(self._samples("set [the] (light|fan)"),
                         sorted(["set light", "set fan",
                                 "set the light", "set the fan"]))

    def test_entity_with_alternatives(self):
        self.assertEqual(self._samples("(buy|purchase) {item}"),
                         sorted(["buy {item}", "purchase {item}"]))

    def test_entity_with_optional(self):
        self.assertEqual(self._samples("eat [some] {fruit}"),
                         sorted(["eat {fruit}", "eat some {fruit}"]))

    # --- deduplication ---

    def test_duplicate_alternatives_deduplicated(self):
        # (a|a) should produce one "a", not two
        self.assertEqual(self._samples("(hello|hello)"), ["hello"])


class TestAccuracyImprovements(unittest.TestCase):
    """Tests for accuracy and speed improvements."""

    def test_keyword_exclusion_word_boundary(self):
        # "play" keyword must not fire when query contains "display" or "replay"
        container = IntentContainer()
        container.add_intent("music", ["play some music"])
        container.add_intent("display", ["show me the display"])
        container.exclude_keywords("music", ["play"])
        # "display" contains "play" as substring — must NOT exclude music via substring
        result = container.calc_intent("show me the display")
        self.assertEqual(result["name"], "display")
        # actual "play" word should still trigger exclusion
        container2 = IntentContainer()
        container2.add_intent("music", ["play some music"])
        container2.add_intent("other", ["do something else"])
        container2.exclude_keywords("music", ["play"])
        result2 = container2.calc_intent("play some music")
        self.assertIsNone(result2["name"])

    def test_wildcard_penalty_proportional(self):
        from padacioso import _wildcard_penalty
        # fully literal — no penalty
        self.assertEqual(_wildcard_penalty("say hello"), 0.0)
        # single wildcard out of 2 tokens: ratio=0.5
        self.assertAlmostEqual(_wildcard_penalty("say *"), 0.15, places=4)
        # single wildcard out of 3 tokens: ratio=1/3
        self.assertAlmostEqual(_wildcard_penalty("say * please"), round(0.05 + 0.20 / 3, 4), places=4)
        # all wildcards: ratio=1.0
        self.assertAlmostEqual(_wildcard_penalty("* *"), 0.25, places=4)
        # entity placeholders alone do NOT count as wildcards
        self.assertEqual(_wildcard_penalty("{item} now"), 0.0)

    def test_tie_breaking_deterministic(self):
        # Two literal intents that match with equal confidence must resolve
        # to the alphabetically-first name, regardless of registration order.
        container = IntentContainer()
        container.add_intent("beta", ["hello world"])
        container.add_intent("alpha", ["hello world"])
        result = container.calc_intent("hello world")
        # _tie_key sorts by (is_literal=0, penalty=0.0, name) → "alpha" wins
        self.assertEqual(result["name"], "alpha")

        # Also verify that reversing registration order does not change the winner
        container2 = IntentContainer()
        container2.add_intent("alpha", ["hello world"])
        container2.add_intent("beta", ["hello world"])
        result2 = container2.calc_intent("hello world")
        self.assertEqual(result2["name"], "alpha")
