import random
import re
from typing import List, Iterator, Optional

import simplematch

from ovos_spec_tools import expand, normalize_for_match


def _normalize(text: str) -> str:
    """Canonical OVOS-INTENT-1 match normalization.

    Delegates to :func:`ovos_spec_tools.normalize_for_match` (lowercase,
    diacritic/punctuation folding, ``{slot}`` markers preserved) and collapses
    internal whitespace exactly as the spec expander does (§4.1). Applied to
    both samples and queries so the two sides compare consistently.

    The ``*`` wildcard token is structural (consumed by simplematch, never
    present in a real utterance) so it is passed through verbatim rather than
    folded away as punctuation.
    """
    normed = []
    for token in text.split():
        normed.append(token if token == "*" else normalize_for_match(token))
    return " ".join(t for t in normed if t)


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


#: Upper bound on expanded samples retained per intent (and per entity).
#: Each expanded sample is resident for the process lifetime as a regex
#: string plus two matcher objects, so an unbounded bracket product in one
#: template can cost gigabytes across a real skill set.
MAX_EXPANSIONS = 2000


class IntentContainer:
    def __init__(self, fuzz=False, n_workers=4):
        self.intent_samples, self.entity_samples = {}, {}
        # OVOS-CONTEXT-1 §7 — per-intent set of declared template slot names,
        # parsed from the ``{slot}`` markers of the samples at registration.
        # Consumed by the pipeline to offer live context entries as slot
        # candidates for slots the utterance itself left unresolved.
        self.intent_slots = {}
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
        self._fuzz_variants = {}  # Pre-computed fuzz variants per regex

        if "word" not in simplematch.types:
            LOG.debug("Registering `word` type")
            _init_sm_word_type()

    @staticmethod
    def _get_fuzzed(sample: str) -> List[str]:
        fuzzed = []
        words = sample.split(" ")
        for idx in range(len(words)):
            if "{" in words[idx] or "}" in words[idx]:
                continue
            new_words = list(words)
            new_words[idx] = "*"
            fuzzed.append(" ".join(new_words))
        return fuzzed + [f"* {sample}", f"{sample} *"]

    @staticmethod
    def _slot_names(patterns: List[str]) -> set:
        """Return the set of ``{slot}`` names declared across the patterns.

        simplematch markers are ``{name}`` or ``{name:type}``; only the name is
        kept. Names are lower-cased to line up with the lower-cased match keys.
        """
        names = set()
        for p in patterns:
            for m in re.finditer(r"\{\s*(\w+)", p):
                names.add(m.group(1).lower())
        return names

    @staticmethod
    def _literal_words(pattern: str) -> frozenset:
        """Return the set of non-entity, non-wildcard words in a pattern."""
        return frozenset(
            w for w in pattern.split()
            if w != "*" and "{" not in w and "}" not in w
        )

    def add_intent(self, name: str, lines: List[str]):
        """
        Add an intent with examples.
        @param name: name of intent to add
        @param lines: list of intent regexes
        """
        if name in self.intent_samples:
            # registrations arrive concurrently from the wire (dual-emit on
            # two contracts, thread-pooled handlers): last write wins
            # (OVOS-INTENT-4 §8.1 replacement), a raise here crashes skill
            # loading on races the caller cannot serialize
            LOG.debug(f"replacing existing intent: {name}")
            self.remove_intent(name)
        # engines own bounding unbounded template data: a bracket product
        # can explode combinatorially, and every expanded sample here costs
        # a resident regex string plus two matcher objects for the lifetime
        # of the process. Spread the budget across the source lines so every
        # template contributes, and sample each line's expansions uniformly
        # (reservoir sampling, seeded deterministically by intent name and
        # line index) rather than keeping only the first N, so a truncated
        # line still contributes coverage from across its whole range.
        expanded = []
        budget = MAX_EXPANSIONS
        per_line = max(1, budget // max(1, len(lines)))
        overflowed_lines = []
        for idx, line in enumerate(lines):
            rng = random.Random(f"{name}:{idx}")
            reservoir = []
            total = 0
            for i, e in enumerate(expand(line)):
                total = i + 1
                if i < per_line:
                    reservoir.append(e)
                else:
                    j = rng.randint(0, i)
                    if j < per_line:
                        reservoir[j] = e
            if total > per_line:
                overflowed_lines.append((idx, line, total))
            expanded.extend(_normalize(e) for e in reservoir)
        if overflowed_lines:
            details = "; ".join(
                f"line {idx} ({line[:40]!r}) expands to {total}"
                for idx, line, total in overflowed_lines
            )
            LOG.warning(f"intent {name!r} expands past {MAX_EXPANSIONS} "
                        f"samples ({details}); sampling {per_line} per line "
                        f"uniformly, keeping {len(expanded)} total (bounded)")
        regexes = list(set(expanded))
        # literal patterns (no entities, no wildcards) first so they can
        # short-circuit before greedy entity patterns consume the query
        regexes.sort(key=lambda r: (0 if "{" not in r and "*" not in r else 1, -len(r)))
        self.intent_samples[name] = regexes
        self.intent_slots[name] = self._slot_names(regexes)
        for r in regexes:
            cm = simplematch.Matcher(r, case_sensitive=True)
            um = simplematch.Matcher(r, case_sensitive=False)
            if r.count("{") >= 2:
                _patch_nongreedy(cm)
                _patch_nongreedy(um)
            self._cased_matchers[r] = cm
            self._uncased_matchers[r] = um
            self._regex_penalty[r] = _wildcard_penalty(r)
            self._fuzz_variants[r] = (
                self._get_fuzzed(r),
                len(r.split()),
                self._literal_words(r),
            )
        self._cache_dirty = True  # Mark cache as needing rebuild

    def remove_intent(self, name: str):
        """
        Remove an intent
        @param name: name of intent to remove
        """
        if name in self.intent_samples:
            regexes = self.intent_samples.pop(name)
            self.intent_slots.pop(name, None)
            for rx in regexes:
                if rx in self._cased_matchers:
                    self._cased_matchers.pop(rx)
                if rx in self._uncased_matchers:
                    self._uncased_matchers.pop(rx)
                self._regex_penalty.pop(rx, None)
                self._fuzz_variants.pop(rx, None)
            self._cache_dirty = True  # Mark cache as needing rebuild

    def add_entity(self, name: str, lines: List[str]):
        """
        Add an entity with examples.
        @param name: name of entity to add
        @param lines: list of entity examples
        """
        if name in self.entity_samples:
            LOG.debug(f"replacing existing entity: {name}")
            self.remove_entity(name)
        name = name.lower()
        expanded = []
        for line in lines:
            if len(expanded) >= MAX_EXPANSIONS:
                LOG.warning(f"entity {name!r} expands past {MAX_EXPANSIONS} "
                            f"values; keeping {len(expanded)} (bounded)")
                break
            expanded += expand(line)[:MAX_EXPANSIONS - len(expanded)]
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
        q_lower = query.lower()
        query_words = set(q_lower.split())
        for intent_name, samples in self.excluded_keywords.items():
            def _kw_hit(kw, _qw=query_words, _ql=q_lower):
                if ' ' not in kw:
                    return kw.lower() in _qw
                return bool(re.search(r'\b' + re.escape(kw.lower()) + r'\b', _ql))
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

    def _entity_member(self, k: str, value) -> bool:
        """Case-insensitive membership of ``value`` in entity ``k``'s samples.

        Queries are lowercased by ``_normalize`` before matching, but a
        registered entity sample keeps whatever case the skill declared it
        with, so a plain ``in`` check would judge a correct, utterance-
        produced value (e.g. "bob") "not a member" of {"Bob"} purely due to
        case — which would then let a live context candidate silently
        overwrite it (violates §7's "utterance value always wins" rule).
        """
        return str(value).lower() in {s.lower() for s in self.entity_samples[k]}

    def _apply_slot_candidate(self, entities, k, v, slot_context, intent_name):
        """OVOS-CONTEXT-1 §7 — offer a live context value as a candidate for
        slot ``k`` BEFORE the entity-membership penalty below is applied.

        The utterance already bound ``v`` to ``k``, but ``v`` is not a member
        of the registered entity's value set. Per §7, a context value supplied
        for that slot must be offered to the matcher before the match is
        finalized rather than patched in afterwards, since a value cannot
        correct a binding that has already incurred its confidence penalty.
        If the context candidate IS a valid entity member, it replaces the
        utterance-extracted value and the penalty is skipped.
        """
        owner_id = intent_name.split(":")[0]
        candidate = slot_context.get((owner_id, k)) if slot_context else None
        if candidate is not None and self._entity_member(k, candidate):
            entities[k] = candidate
            return True
        return False

    def _match(self, query, intent_name, regexes, slot_context=None):
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
                    elif not self._entity_member(k, v):
                        if self._apply_slot_candidate(entities, k, v, slot_context, intent_name):
                            continue
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
                    elif not self._entity_member(k, v):
                        if self._apply_slot_candidate(entities, k, v, slot_context, intent_name):
                            continue
                        # penalize parsed entity value not in samples
                        penalty += 0.1
                return {"entities": entities or {}, "conf": round(max(0.0, 1.0 - penalty), 4), "name": intent_name, "_matched_regex": r}

        if self.fuzz:
            query_words = query.split()
            query_word_set = frozenset(query_words)
            query_len = len(query_words)
            for r in regexes:
                variants, pat_len, literal_words = self._fuzz_variants.get(
                    r, (self._get_fuzzed(r), len(r.split()), self._literal_words(r))
                )
                # skip patterns whose length differs too much from the query
                if abs(pat_len - query_len) > max(2, query_len // 2):
                    continue
                # skip patterns with no literal words in common with the query
                if literal_words and not literal_words.intersection(query_word_set):
                    continue
                for s in variants:
                    entities = self._fuzzy_score(query, s, 0.25)
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

    def calc_intents(self, query: str, slot_context=None) -> Iterator[dict]:
        """
        Determine possible intents for a given query
        @param query: input to evaluate for an intent match
        @param slot_context: OVOS-CONTEXT-1 §7 — optional mapping of
            ``(owner_id, slot_name) -> value`` of live session context
            candidates, offered to the matcher before it resolves competing
            regex candidates
        @return: yields dict intent matches
        """
        query = _normalize(query)

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
            res = self._match(query, intent_name, regexes, slot_context)
            if res is not None:
                yield res

    def calc_intent(self, query: str) -> Optional[dict]:
        """
        Determine the best intent match for a given query
        @param query: input to evaluate for an intent
        @return: dict matched intent (or None)
        """
        _GOOD_ENOUGH = 0.95
        match = {"name": None, "entities": {}}
        best_conf = 0.0
        best_is_literal = False
        can_short_circuit = False
        intents = []
        for res in self.calc_intents(query):
            if res is None or not res.get("name"):
                continue
            conf = res.get("conf", 0)
            # If we already have a good-enough literal, collect ties but stop
            # as soon as a lower-confidence candidate arrives so the tie-breaker
            # always sees every candidate that shares the winning confidence.
            if can_short_circuit and conf < best_conf:
                break
            intents.append(res)
            if conf > best_conf:
                best_conf = conf
                r = res.get("_matched_regex", "")
                best_is_literal = "{" not in r and "*" not in r
            # Only arm the short-circuit once we have a literal at >= 0.95.
            # An entity match at 0.96 must not block a literal (conf=1.0) later.
            if best_conf >= _GOOD_ENOUGH and best_is_literal:
                can_short_circuit = True

        if not intents:
            LOG.info("No match")
            return match

        best_conf = max(x.get("conf", 0) for x in intents)
        ties = [i for i in intents if i.get("conf", 0) == best_conf]

        if len(ties) > 1:
            LOG.info(f"tied intents: {[t['name'] for t in ties]}")
            def _tie_key(t):
                r = t.get("_matched_regex", "")
                is_literal = "{" not in r and "*" not in r
                return (
                    0 if is_literal else 1,  # literal beats entity/wildcard
                    self._regex_penalty.get(r, 1.0),
                    t["name"],
                )
            ties.sort(key=_tie_key)

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
