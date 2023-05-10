import simplematch

from typing import List, Iterator, Optional
from padacioso.bracket_expansion import expand_parentheses, clean_braces

try:
    from ovos_utils.log import LOG
except ImportError:
    import logging
    LOG = logging.getLogger('padacioso')


class IntentContainer:
    def __init__(self, fuzz=False):
        self.intent_samples, self.entity_samples = {}, {}
        # self.intents, self.entities = {}, {}
        self.fuzz = fuzz
        self._cased_matchers = dict()
        self._uncased_matchers = dict()

    @staticmethod
    def _get_fuzzed(sample: str) -> List[str]:
        """
        Get fuzzy match examples by allowing a wildcard in place of each
        specified word.
        @param sample: Utterance example to mutate
        @return: list of fuzzy string alternatives to `sample`
        """
        fuzzed = []
        words = sample.split(" ")
        for idx in range(0, len(words)):
            if "{" in words[idx] or "}" in words[idx]:
                continue
            new_words = list(words)
            new_words[idx] = "*"
            fuzzed.append(" ".join(new_words))
        return fuzzed + [f"* {sample}", f"{sample} *"]

    def add_intent(self, name: str, lines: List[str]):
        """
        Add an intent with examples.
        @param name: name of intent to add
        @param lines: list of intent regexes
        """
        if name in self.intent_samples:
            raise RuntimeError(f"Attempted to re-register existing intent: "
                               f"{name}")
        expanded = []
        for l in lines:
            expanded += expand_parentheses(clean_braces(l))
        regexes = list(set(expanded))
        regexes.sort(key=len, reverse=True)
        self.intent_samples[name] = regexes
        for r in regexes:
            self._cased_matchers[r] = \
                simplematch.Matcher(r, case_sensitive=True)
            self._uncased_matchers[r] = \
                simplematch.Matcher(r, case_sensitive=False)

    def remove_intent(self, name: str):
        """
        Remove an intent
        @param name: name of intent to remove
        """
        if name in self.intent_samples:
            regexes = self.intent_samples.pop(name)
            for rx in regexes:
                if rx in self._cased_matchers:
                    self._cased_matchers.pop(rx)
                if rx in self._uncased_matchers:
                    self._uncased_matchers.pop(rx)

    def add_entity(self, name: str, lines: List[str]):
        """
        Add an entity with examples.
        @param name: name of entity to add
        @param lines: list of entity examples
        """
        if name in self.entity_samples:
            raise RuntimeError(f"Attempted to re-register existing entity: "
                               f"{name}")
        name = name.lower()
        expanded = []
        for l in lines:
            expanded += expand_parentheses(l)
        self.entity_samples[name] = expanded

    def remove_entity(self, name: str):
        """
        Remove an entity
        @param name: name of entity to remove
        """
        name = name.lower()
        if name in self.entity_samples:
            del self.entity_samples[name]

    def calc_intents(self, query: str) -> Iterator[dict]:
        """
        Determine possible intents for a given query
        @param query: input to evaluate for an intent match
        @return: yields dict intent matches
        """
        for intent_name, regexes in self.intent_samples.items():
            for r in regexes:
                penalty = 0
                if "*" in r:
                    # penalize wildcards
                    penalty = 0.15
                if r not in self._cased_matchers:
                    LOG.warning(f"{r} not initialized")
                    self._cased_matchers[r] = \
                        simplematch.Matcher(r, case_sensitive=True)
                entities = self._cased_matchers[r].match(query)
                if entities is not None:
                    for k, v in entities.items():
                        if k not in self.entity_samples:
                            # penalize unregistered entities
                            penalty += 0.04
                        elif str(v) not in self.entity_samples[k]:
                            # penalize parsed entity value not in samples
                            penalty += 0.1
                    yield {"entities": entities or {},
                           "conf": 1 - penalty,
                           "name": intent_name}
                    break

                if r not in self._uncased_matchers:
                    LOG.warning(f"{r} not initialized")
                    self._uncased_matchers[r] = \
                        simplematch.Matcher(r, case_sensitive=False)
                entities = self._uncased_matchers[r].match(query)
                if entities is not None:
                    # penalize case mismatch
                    penalty += 0.05
                    for k, v in entities.items():
                        if k not in self.entity_samples:
                            # penalize unregistered entities
                            penalty += 0.05
                        elif str(v) not in self.entity_samples[k]:
                            # penalize parsed entity value not in samples
                            penalty += 0.1
                    yield {"entities": entities or {},
                           "conf": 1 - penalty,
                           "name": intent_name}
                    break

                if self.fuzz:
                    LOG.debug(f"Fallback to fuzzy match")
                    penalty += 0.25
                    for f in self._get_fuzzed(r):
                        entities = simplematch.match(f, query,
                                                     case_sensitive=False)
                        if entities is not None:
                            yield {"entities": entities or {},
                                   "conf": 1 - penalty,
                                   "name": intent_name}
                            break

    def calc_intent(self, query: str) -> Optional[dict]:
        """
        Determine the best intent match for a given query
        @param query: input to evaluate for an intent
        @return: dict matched intent (or None)
        """
        match = max(
            self.calc_intents(query),
            key=lambda x: x["conf"],
            default={'name': None, 'entities': {}}
        )
        for entity in set(match['entities'].keys()):
            entities = match['entities'].pop(entity)
            match['entities'][entity.lower()] = entities
        LOG.debug(match)
        return match
