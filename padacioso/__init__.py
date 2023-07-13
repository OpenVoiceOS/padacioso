import concurrent.futures
from typing import List, Iterator, Optional

import simplematch

from padacioso.bracket_expansion import expand_parentheses, normalize_example

try:
    from ovos_utils.log import LOG
    from ovos_utils.parse import fuzzy_match  # uses rapidfuzz for performance
except ImportError:
    import logging

    LOG = logging.getLogger('padacioso')

    from difflib import SequenceMatcher


    def fuzzy_match(x, against):
        """Perform a 'fuzzy' comparison between two strings.
        Returns:
            float: match percentage -- 1.0 for perfect match,
                   down to 0.0 for no match at all.
        """
        return SequenceMatcher(None, x, against).ratio()


class IntentContainer:
    def __init__(self, fuzz=False, n_workers=4):
        self.intent_samples, self.entity_samples = {}, {}
        # self.intents, self.entities = {}, {}
        self.fuzz = fuzz
        self.workers = n_workers
        self._cased_matchers = {}
        self._uncased_matchers = {}
        self.available_contexts = {}
        self.required_contexts = {}
        self.excluded_keywords = {}
        self.excluded_contexts = {}

        if "word" not in simplematch.types:
            LOG.debug(f"Registering `word` type")
            _init_sm_word_type()

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
            expanded += expand_parentheses(normalize_example(l))
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

    def _filter(self, query: str):
        # filter intents based on context/excluded keywords
        excluded_intents = []
        for intent_name, samples in self.excluded_keywords.items():
            if any(s in query for s in samples):
                excluded_intents.append(intent_name)
        for intent_name, contexts in self.required_contexts.items():
            if intent_name not in self.available_contexts:
                excluded_intents.append(intent_name)
            elif any(context not in self.available_contexts[intent_name]
                     for context in contexts):
                excluded_intents.append(intent_name)
        for intent_name, contexts in self.excluded_contexts.items():
            if intent_name not in self.available_contexts:
                continue
            if any(context in self.available_contexts[intent_name]
                   for context in contexts):
                excluded_intents.append(intent_name)
        return excluded_intents

    def _match(self, query, intent_name, regexes):
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
                return {"entities": entities or {},
                        "conf": 1 - penalty,
                        "name": intent_name}

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
                return {"entities": entities or {},
                        "conf": 1 - penalty,
                        "name": intent_name}

        if self.fuzz:
            for r in regexes:
                penalty = 0.25
                for s in self._get_fuzzed(r):
                    entities = self._fuzzy_score(query, s, penalty)
                    if entities:
                        entities["name"] = intent_name
                        return entities

    def _fuzzy_score(self, query, s, penalty=0.25):
        entities = simplematch.match(s, query, case_sensitive=False)

        fuzzy_penalty = penalty
        if "*" in s:  # very loose regex
            fuzzy_penalty += 0.1
        if "{" in s:  # capture group
            fuzzy_penalty += 0.05
        # depending on length
        diff = max(len(s) - len(query), 0)
        fuzzy_penalty += diff * 0.01
        base_score = 1 - max(1 - fuzzy_penalty, 0)
        fuzzy_score = fuzzy_match(s, query)
        score = (fuzzy_score + base_score) / 2

        if entities is not None:
            return {"entities": entities or {},
                    "conf": (fuzzy_score + base_score) / 2}

    def calc_intents(self, query: str) -> Iterator[dict]:
        """
        Determine possible intents for a given query
        @param query: input to evaluate for an intent match
        @return: yields dict intent matches
        """
        # filter intents based on context/excluded keywords
        excluded_intents = self._filter(query)

        # do the work in parallel instead of sequentially
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.workers) as executor:
            future_to_source = {
                executor.submit(self._match, query, intent_name, regexes): intent_name
                for intent_name, regexes in self.intent_samples.items() if intent_name not in excluded_intents
            }
            for future in concurrent.futures.as_completed(future_to_source):
                res = future.result()
                if res is not None:
                    yield res

    def calc_intent(self, query: str) -> Optional[dict]:
        """
        Determine the best intent match for a given query
        @param query: input to evaluate for an intent
        @return: dict matched intent (or None)
        """
        match = {'name': None, 'entities': {}}
        intents = [i for i in self.calc_intents(query) if i is not None and i.get("name")]
        if len(intents) == 0:
            LOG.info("No match")
            return match

        best_conf = max(x.get("conf", 0) for x in intents if x.get("name"))
        ties = [i for i in intents if i.get("conf", 0) == best_conf]

        if len(ties) > 1:
            # TODO - how to untie?
            LOG.info(f"tied intents: {ties}")

        match = ties[0]

        for entity in set(match['entities'].keys()):
            entities = match['entities'].pop(entity)
            match['entities'][entity.lower()] = entities
        LOG.debug(match)
        return match

    def exclude_keywords(self, intent_name, samples):
        if intent_name not in self.excluded_keywords:
            self.excluded_keywords[intent_name] = samples
        else:
            self.excluded_keywords[intent_name] += samples

    def set_context(self, intent_name, context_name, context_val=None):
        if intent_name not in self.available_contexts:
            self.available_contexts[intent_name] = {}
        self.available_contexts[intent_name][context_name] = context_val

    def exclude_context(self, intent_name, context_name):
        if intent_name not in self.excluded_contexts:
            self.excluded_contexts[intent_name] = [context_name]
        else:
            self.excluded_contexts[intent_name].append(context_name)

    def unexclude_context(self, intent_name, context_name):
        if intent_name in self.excluded_contexts:
            self.excluded_contexts[intent_name] = [c for c in self.excluded_contexts[intent_name]
                                                   if context_name != c]

    def unset_context(self, intent_name, context_name):
        if intent_name in self.available_contexts:
            if context_name in self.available_contexts[intent_name]:
                self.available_contexts[intent_name].pop(context_name)

    def require_context(self, intent_name, context_name):
        if intent_name not in self.required_contexts:
            self.required_contexts[intent_name] = [context_name]
        else:
            self.required_contexts[intent_name].append(context_name)

    def unrequire_context(self, intent_name, context_name):
        if intent_name in self.required_contexts:
            self.required_contexts[intent_name] = [c for c in self.required_contexts[intent_name]
                                                   if context_name != c]


def _init_sm_word_type():
    """
    Registers a `word` type with SimpleMatch to support Padatious `:0` syntax
    """
    regex = r"[a-zA-Z0-9]+"
    simplematch.register_type("word", regex)
