import re
from typing import List, Iterator, Optional

import simplematch

from padacioso.bracket_expansion import expand_parentheses, normalize_example, normalize_utterance, _space_entities


def _wildcard_penalty(pattern: str) -> float:
    """Compute a wildcard penalty proportional to how much of the pattern is wildcards.

    Only `*` tokens are counted; entity placeholders have their own penalty path.
    Fully literal (or entity-only) patterns return 0.
    Range: [0.05, 0.25] when any `*` token exists, 0 otherwise.
    """
    tokens = pattern.split()
    if not tokens:
        return 0.0
    wildcard_tokens = sum(1 for t in tokens if "*" in t)
    if wildcard_tokens == 0:
        return 0.0
    ratio = wildcard_tokens / len(tokens)
    return round(0.05 + 0.20 * ratio, 4)

def _patch_nongreedy(matcher) -> None:
    """Switch named capture groups to non-greedy for multi-entity patterns.

    Prevents the first entity from consuming tokens that belong to later ones
    when no literal separator exists between placeholders.
    """
    fixed = re.sub(r'\(\?P<(\w+)>\.\*\)', r'(?P<\1>.*?)', matcher.regex)
    if fixed != matcher.regex:
        matcher.regex = fixed


try:
    from ovos_utils.log import LOG
    from ovos_utils.parse import fuzzy_match  # uses rapidfuzz for performance
except ImportError:
    import logging

    LOG = logging.getLogger("padacioso")

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

        # Cache for optimization - pre-built list for fast iteration
        self._intent_list = []  # Pre-built list of (intent_name, regexes)
        self._cache_dirty = True  # Flag to rebuild cache on next query
        self._regex_penalty = {}  # Per-regex wildcard penalty

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
            raise RuntimeError(f"Attempted to re-register existing intent: {name}")
        expanded = []
        for l in lines:
            for e in expand_parentheses(normalize_example(l)):
                expanded.append(normalize_utterance(_space_entities(e)))
        regexes = list(set(expanded))
        regexes.sort(key=len, reverse=True)
        self.intent_samples[name] = regexes
        for r in regexes:
            cm = simplematch.Matcher(r, case_sensitive=True)
            um = simplematch.Matcher(r, case_sensitive=False)
            if r.count("{") >= 2:
                _patch_nongreedy(cm)
                _patch_nongreedy(um)
            self._cased_matchers[r] = cm
            self._uncased_matchers[r] = um
            self._regex_penalty[r] = _wildcard_penalty(r)
        self._cache_dirty = True  # Mark cache as needing rebuild

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
                self._regex_penalty.pop(rx, None)
            self._cache_dirty = True  # Mark cache as needing rebuild

    def add_entity(self, name: str, lines: List[str]):
        """
        Add an entity with examples.
        @param name: name of entity to add
        @param lines: list of entity examples
        """
        if name in self.entity_samples:
            raise RuntimeError(f"Attempted to re-register existing entity: {name}")
        name = name.lower()
        expanded = []
        for l in lines:
            expanded += expand_parentheses(l)
        self.entity_samples[name] = set(expanded)
        self._cache_dirty = True  # Mark cache as needing rebuild

    def remove_entity(self, name: str):
        """
        Remove an entity
        @param name: name of entity to remove
        """
        name = name.lower()
        if name in self.entity_samples:
            del self.entity_samples[name]

    def _rebuild_cache(self):
        """
        Rebuild cached intent metadata for fast filtering.
        Called lazily on first query after registration to avoid O(n²) during bulk registration.
        """
        # Pre-build the intent list to avoid reconstructing it every query
        self._intent_list = list(self.intent_samples.items())
        self._cache_dirty = False

    def _filter(self, query: str):
        # filter intents based on context/excluded keywords
        excluded_intents = []
        query_words = set(query.lower().split())
        for intent_name, samples in self.excluded_keywords.items():
            def _kw_hit(kw, _qw=query_words, _q=query):
                if ' ' not in kw:
                    return kw.lower() in _qw
                return bool(re.search(r'\b' + re.escape(kw.lower()) + r'\b', _q))
            if any(_kw_hit(s) for s in samples):
                excluded_intents.append(intent_name)
        for intent_name, contexts in self.required_contexts.items():
            if intent_name not in self.available_contexts:
                excluded_intents.append(intent_name)
            elif any(context not in self.available_contexts[intent_name] for context in contexts):
                excluded_intents.append(intent_name)
        for intent_name, contexts in self.excluded_contexts.items():
            if intent_name not in self.available_contexts:
                continue
            if any(context in self.available_contexts[intent_name] for context in contexts):
                excluded_intents.append(intent_name)
        return excluded_intents

    def _match(self, query, intent_name, regexes):
        query_has_upper = query != query.lower()
        for r in regexes:
            penalty = self._regex_penalty.get(r, 0.0)
            entities = None

            if query_has_upper:
                if r not in self._cased_matchers:
                    LOG.warning(f"{r} not initialized")
                    cm = simplematch.Matcher(r, case_sensitive=True)
                    if r.count("{") >= 2:
                        _patch_nongreedy(cm)
                    self._cased_matchers[r] = cm
                    self._regex_penalty.setdefault(r, _wildcard_penalty(r))
                entities = self._cased_matchers[r].match(query)

            if entities is not None:
                for k, v in entities.items():
                    if k not in self.entity_samples:
                        # penalize unregistered entities
                        penalty += 0.04
                    elif str(v) not in self.entity_samples[k]:
                        # penalize parsed entity value not in samples
                        penalty += 0.1
                return {"entities": entities or {}, "conf": round(max(0.0, 1.0 - penalty), 4), "name": intent_name, "_matched_regex": r}

            if r not in self._uncased_matchers:
                LOG.warning(f"{r} not initialized")
                um = simplematch.Matcher(r, case_sensitive=False)
                if r.count("{") >= 2:
                    _patch_nongreedy(um)
                self._uncased_matchers[r] = um
                self._regex_penalty.setdefault(r, _wildcard_penalty(r))
            entities = self._uncased_matchers[r].match(query)
            if entities is not None:
                # query_has_upper + uncased match = genuine case mismatch
                entity_penalty = 0.04 if not query_has_upper else 0.05
                if query_has_upper:
                    penalty += 0.05
                for k, v in entities.items():
                    if k not in self.entity_samples:
                        # penalize unregistered entities
                        penalty += entity_penalty
                    elif str(v) not in self.entity_samples[k]:
                        # penalize parsed entity value not in samples
                        penalty += 0.1
                return {"entities": entities or {}, "conf": round(max(0.0, 1.0 - penalty), 4), "name": intent_name, "_matched_regex": r}

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
            return {"entities": entities or {}, "conf": score}

    def calc_intents(self, query: str) -> Iterator[dict]:
        """
        Determine possible intents for a given query
        @param query: input to evaluate for an intent match
        @return: yields dict intent matches
        """
        query = normalize_utterance(query)

        # Lazy cache rebuild - only rebuild once after bulk registration
        # This avoids O(n²) scaling during registration (rebuild on every add)
        if self._cache_dirty:
            self._rebuild_cache()

        # Filter based on runtime context/keywords (query and session dependent)
        excluded_intents = self._filter(query)

        # Sequential processing - threading overhead > actual work for regex matching
        for intent_name, regexes in self._intent_list:
            if intent_name in excluded_intents:
                continue
            res = self._match(query, intent_name, regexes)
            if res is not None:
                yield res
                # Early exit optimization: perfect match found
                # TODO: Some validation that we don't have duplicates, and warning if we do
                if res.get("conf", 0) == 1.0:
                    return

    def calc_intent(self, query: str) -> Optional[dict]:
        """
        Determine the best intent match for a given query
        @param query: input to evaluate for an intent
        @return: dict matched intent (or None)
        """
        _GOOD_ENOUGH = 0.95
        match = {"name": None, "entities": {}}
        best_conf = 0.0
        intents = []
        for res in self.calc_intents(query):
            if res is None or not res.get("name"):
                continue
            intents.append(res)
            if res.get("conf", 0) > best_conf:
                best_conf = res["conf"]
            if best_conf >= _GOOD_ENOUGH:
                break

        if not intents:
            LOG.info("No match")
            return match

        best_conf = max(x.get("conf", 0) for x in intents)
        ties = [i for i in intents if i.get("conf", 0) == best_conf]

        if len(ties) > 1:
            LOG.info(f"tied intents: {[t['name'] for t in ties]}")
            ties.sort(key=lambda t: (
                self._regex_penalty.get(t.get("_matched_regex", ""), 1.0),
                t["name"]
            ))

        match = dict(ties[0])
        match.pop("_matched_regex", None)

        for entity in set(match["entities"].keys()):
            entities = match["entities"].pop(entity)
            match["entities"][entity.lower()] = entities
        LOG.debug(match)
        return match

    def exclude_keywords(self, intent_name, samples):
        if intent_name not in self.excluded_keywords:
            self.excluded_keywords[intent_name] = samples
        else:
            self.excluded_keywords[intent_name] += samples
        self._cache_dirty = True  # Mark cache as needing rebuild

    def set_context(self, intent_name, context_name, context_val=None):
        if intent_name not in self.available_contexts:
            self.available_contexts[intent_name] = {}
        self.available_contexts[intent_name][context_name] = context_val

    def exclude_context(self, intent_name, context_name):
        if intent_name not in self.excluded_contexts:
            self.excluded_contexts[intent_name] = [context_name]
        else:
            self.excluded_contexts[intent_name].append(context_name)
        self._cache_dirty = True  # Mark cache as needing rebuild

    def unexclude_context(self, intent_name, context_name):
        if intent_name in self.excluded_contexts:
            self.excluded_contexts[intent_name] = [c for c in self.excluded_contexts[intent_name] if context_name != c]
        self._cache_dirty = True  # Mark cache as needing rebuild

    def unset_context(self, intent_name, context_name):
        if intent_name in self.available_contexts:
            if context_name in self.available_contexts[intent_name]:
                self.available_contexts[intent_name].pop(context_name)

    def require_context(self, intent_name, context_name):
        if intent_name not in self.required_contexts:
            self.required_contexts[intent_name] = [context_name]
        else:
            self.required_contexts[intent_name].append(context_name)
        self._cache_dirty = True  # Mark cache as needing rebuild

    def unrequire_context(self, intent_name, context_name):
        if intent_name in self.required_contexts:
            self.required_contexts[intent_name] = [c for c in self.required_contexts[intent_name] if context_name != c]
            self._cache_dirty = True  # Mark cache as needing rebuild


def _init_sm_word_type():
    """
    Registers a `word` type with SimpleMatch to support Padatious `:0` syntax
    """
    regex = r"[a-zA-Z0-9]+"
    simplematch.register_type("word", regex)
