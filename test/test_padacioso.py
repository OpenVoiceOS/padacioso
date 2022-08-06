from padacioso import IntentContainer
import unittest


class TestIntentContainer(unittest.TestCase):
    # test intent syntax
    def test_one_of(self):
        container = IntentContainer()
        container.add_intent('hello', ["(hello|hi|hey) world"])
        self.assertEqual(container.intent_samples["hello"],
                         ['hello world', 'hi world', 'hey world'])

    def test_optionally(self):
        container = IntentContainer()
        container.add_intent('hello', ["hello (world|)"])
        self.assertEqual(container.intent_samples["hello"],
                         ['hello world', 'hello'])

        container.add_intent('hey', ["hey [world]"])
        self.assertEqual(container.intent_samples["hey"],
                         ['hey world', 'hey'])

        container.add_intent('hi', ["hi [{person}|people]"])
        self.assertEqual(container.intent_samples["hi"],
                         ['hi {person}', 'hi people', 'hi'])

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
            "conf": 0.95  # unseen entity example
        })
        self.assertEqual(container.calc_intent('eat some bananas'), {
            'name': 'eat', 'entities': {'fruit': 'bananas'},
            "conf": 0.9  # unregistered entity
        })

    def test_case(self):
        container = IntentContainer()
        container.add_intent('test', ['Testing cAPitalizAtion'])
        self.assertEqual(
            container.calc_intent('Testing cAPitalizAtion')['conf'], 1.0)
        self.assertEqual(
            container.calc_intent('teStiNg CapitalIzation')['conf'], 0.95)

    def test_multiple_entities(self):
        container = IntentContainer()
        container.add_intent('test3', ['I see {thing} (in|on) {place}'])
        self.assertEqual(
            container.calc_intent('I see a bin in there'),
            {'conf': 0.8,  # unregistered entity * 2
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

    def test_typed_entities(self):
        container = IntentContainer()
        container.add_intent('test_int', ['* number {number:int}'])
        self.assertEqual(
            container.calc_intent('i want nuMBer 3'),
            {'conf': 0.7,  # wildcard + unregistered entity + bad case
             'entities': {'number': 3}, 'name': 'test_int'})
        self.assertEqual(
            container.calc_intent('i want number 3'),
            {'conf': 0.75,  # wildcard + unregistered entity
             'entities': {'number': 3}, 'name': 'test_int'})

        container.add_entity("number", ["1", "2", "3", "4", "5"])
        self.assertEqual(
            container.calc_intent('i want number 10'),
            {'conf': 0.8,  # wildcard + unseen entity example
             'entities': {'number': 10}, 'name': 'test_int'})
        self.assertEqual(
            container.calc_intent('i want number 3'),
            {'conf': 0.85,  # wildcard + registered entity sample
             'entities': {'number': 3}, 'name': 'test_int'})
        self.assertEqual(
            container.calc_intent('i want numBeR 3'),
            {'conf': 0.8,  # wildcard + registered entity sample + bad case
             'entities': {'number': 3}, 'name': 'test_int'})

        container.add_intent('test_float', ['* float {number:float}'])
        self.assertEqual(
            container.calc_intent('i want float 3'),
            {'conf': 0.8,   # wildcard + unseen entity example
             'entities': {'number': 3.0}, 'name': 'test_float'})

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

        # regex match
        intent = container.calc_intent("tell me about Mycroft")
        self.assertEqual(intent["name"], "test2")
        self.assertEqual(intent["entities"], {'thing': 'Mycroft'})

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
        self.assertEqual(intent["entities"], {'thing': 'Mycroft'})

        # fuzzy match
        intent = container.calc_intent("this is test")
        self.assertEqual(intent["name"], "test")

        # fuzzy regex match
        intent = container.calc_intent("tell me everything about Mycroft")
        self.assertEqual(intent["name"], "test2")
        self.assertEqual(intent["entities"], {'thing': 'Mycroft'})

