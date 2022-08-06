import simplematch
import logging
from padacioso.bracket_expansion import expand_parentheses
LOG = logging.getLogger('padacioso')


class IntentContainer:
    def __init__(self, fuzz=False):
        self.intent_samples, self.entity_samples = {}, {}
        self.intents, self.entities = {}, {}
        self.fuzz = fuzz

    def add_intent(self, name, lines):
        expanded = []
        for l in lines:
            expanded += expand_parentheses(l)
        self.intent_samples[name] = list(set(expanded))

    def _get_fuzzed(self, sample):
        fuzzed = []
        words = sample.split(" ")
        for idx in range(0, len(words)):
            if "{" in words[idx] or "}" in words[idx]:
                continue
            new_words = list(words)
            new_words[idx] = "*"
            fuzzed.append(" ".join(new_words))
        return fuzzed + [f"* {sample}", f"{sample} *"]

    def remove_intent(self, name):
        if name in self.intent_samples:
            del self.intent_samples[name]

    def add_entity(self, name, lines):
        expanded = []
        for l in lines:
            expanded += expand_parentheses(l)
        self.entity_samples[name] = expanded

    def remove_entity(self, name):
        if name in self.entity_samples:
            del self.entity_samples[name]

    def calc_intents(self, query):
        for intent_name, regexes in self.intent_samples.items():
            regexes = sorted(regexes, key=len, reverse=True)
            for r in regexes:
                penalty = 0
                if "*" in r:
                    # penalize wildcards
                    penalty = 0.15

                entities = simplematch.match(r, query, case_sensitive=True)
                if entities is not None:
                    for k, v in entities.items():
                        if k not in self.entity_samples:
                            # penalize unregistered entities
                            penalty += 0.1
                        elif str(v) not in self.entity_samples[k]:
                            # penalize unknown samples
                            penalty += 0.05
                    yield {"entities": entities or {},
                           "conf": 1 - penalty,
                           "name": intent_name}
                    break

                entities = simplematch.match(r, query, case_sensitive=False)
                if entities is not None:
                    # penalize case mismatch
                    penalty += 0.05
                    for k, v in entities.items():
                        if k not in self.entity_samples:
                            # penalize unregistered entities
                            penalty += 0.1
                        elif str(v) not in self.entity_samples[k]:
                            # penalize unknown samples
                            penalty += 0.05
                    yield {"entities": entities or {},
                           "conf": 1 - penalty,
                           "name": intent_name}
                    break

                if self.fuzz:
                    penalty += 0.25
                    for f in self._get_fuzzed(r):
                        entities = simplematch.match(f, query, case_sensitive=False)
                        if entities is not None:
                            yield {"entities": entities or {},
                                   "conf": 1 - penalty,
                                   "name": intent_name}
                            break

    def calc_intent(self, query):
        return max(
            self.calc_intents(query),
            key=lambda x: x["conf"],
            default={'name': None, 'entities': {}}
        )
