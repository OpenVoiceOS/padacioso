import random
import re
from functools import lru_cache
from typing import Dict, List, Iterator, Optional, Tuple

import simplematch

from ovos_spec_tools import expand, normalize_for_match


@lru_cache(maxsize=None)
def _separates_words(char: str) -> bool:
    """True if *char* is a mark the fold turns into a word boundary.

    Asked of :func:`ovos_spec_tools.normalize_for_match` rather than decided
    here, so this file never holds a second copy of the rule: a character
    placed between two letters either leaves one word or leaves two, and the
    fold itself is the only thing that knows which. A separating mark (``,``,
    ``،``, ``。``) gives ``"a b"``; a mark the fold deletes (an apostrophe, an
    interpunct, ``_``) gives ``"ab"``; a letter gives neither.
    """
    return normalize_for_match(f"a{char}b") == "a b"


def _word_spans(token: str, offset: int = 0) -> Iterator[Tuple[int, int]]:
    """Spans of one whitespace token's words, where the fold puts a boundary.

    Yields ``(start, end)`` into the text the token was cut from, *offset*
    being where the token sits there. ``"Åsa,please"`` is two words to the
    fold, so it must be two words here. Runs of separators collapse and
    leading or trailing ones drop, which is what the fold's own whitespace
    collapse does.

    A ``{slot}`` span is atomic, exactly as `normalize_for_match` keeps it:
    its braces are `Ps`/`Pe` and would otherwise separate, which would reduce
    ``"{name}"`` to ``"name"`` and silently turn the marker into a literal
    word, so the template would stop capturing anything at all. Inside a word
    it counts as letters do: ``"{schedkind}-inu"`` stays one word, because
    the fold keeps ``"alarme-inu"`` one word and the template must fold the
    way the utterance does.
    """
    start = end = None
    for match in re.finditer(r"\{[^{}]*\}|.", token, re.DOTALL):
        if len(match.group()) == 1 and _separates_words(match.group()):
            if start is not None:
                yield offset + start, offset + end
                start = None
            continue
        if start is None:
            start = match.start()
        end = match.end()
    if start is not None:
        yield offset + start, offset + end


def _normalize_tokens(text: str):
    """Match-normalized words beside the spans of *text* they were read from.

    The two lists are the same length and aligned by index: element *i* of the
    first is what the text at span *i* folds to. A word that folds away to
    nothing (bare punctuation) is dropped from BOTH, so the alignment holds.

    The alignment is what lets a captured slot value be reported as the words
    the user actually said. OVOS-INTENT-1 §5.2 says the engine "captures a
    span of the utterance", and §5.3 that a slot "still fills with the surface
    words the user spoke". Matching wants the folded form; the value does not.

    One whitespace token is not always one word. OVOS-INTENT-2 §4.3 counts
    whole words, so `normalize_for_match` replaces a word-separating mark with
    a space (ovos-spec-tools, from architecture's T-7149): ``"Åsa,please"``
    folds to ``"asa please"``. Pairing that by index against the single
    whitespace token put a two-word string in a list whose reader assumes one
    word per entry, and `_surface_value` then failed to find the span and
    handed back the folded form - ``"asa please"`` for a name the user gave as
    ``"Åsa"``, which is the harm T-5676 fixed. So a token is cut on the same
    boundaries first, and each word is folded on its own. Every entry is one
    word by construction, whatever the fold does.

    Spans rather than the words themselves, because `_surface_value` reports
    the utterance text between the first and last word of a captured run
    (§5.6: ``utterance[start:end] == surface``). Rejoining words with single
    spaces drops whatever stood between them, which turns a date the user
    gave as ``"March 3, 2027"`` into ``"March 3 2027"`` - no longer a span of
    the utterance, so a consumer looking a typed slot up by surface equality
    finds nothing.
    """
    normed, spans = [], []
    for match in re.finditer(r"\S+", text):
        if match.group() == "*":
            # structural wildcard, consumed by simplematch and never spoken
            normed.append(match.group())
            spans.append((match.start(), match.end()))
            continue
        for start, end in _word_spans(match.group(), match.start()):
            folded = normalize_for_match(text[start:end])
            if folded:
                normed.append(folded)
                spans.append((start, end))
    return normed, spans


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
    return " ".join(_normalize_tokens(text)[0])


def _surface_value(value, normed, spans, text, cursor: int = 0):
    """*value*, a span of the folded query, as the words the user spoke.

    Returns ``(surface_value, next_cursor)``. The captured span is a run of
    whole folded words, so its surface form is *text* between the start of the
    run's first word and the end of its last: the words the user said, with
    their diacritics, their case and whatever stood between them.

    The search starts at *cursor*, the token after the previous slot's span, so
    two slots that fold to the same run each report their own words: in
    ``"röd och rod"`` the first slot is ``röd`` and the second ``rod``, where a
    search from zero would report ``röd`` twice. A value not found from the
    cursor is searched for from the start, since nothing guarantees the
    matcher hands its slots back in the order they appear.

    A value that is no run of the folded query at all is returned unchanged:
    the matcher supplied it from a registered entity or from session context
    rather than cutting it out of the utterance, and it is not this function's
    to rewrite.
    """
    if not isinstance(value, str) or not value:
        return value, cursor
    want = value.split()
    if not want:
        return value, cursor
    last = len(normed) - len(want)
    for first in (cursor, 0):
        for start in range(first, last + 1):
            if normed[start:start + len(want)] == want:
                # the span exactly as the user said it, case included, and a
                # span of the utterance by construction (§5.6).
                # OVOS-INTENT-1 §2 asks an upstream stage to lowercase the
                # utterance before it reaches an engine, and in the fleet it
                # does not: "lösche meinen Alarm für Zahnarzt" arrives with its
                # capital. Folding it here destroyed a name the user gave, and a
                # consumer that wants a folded form can fold what it is handed,
                # while a consumer handed the folded form cannot recover the
                # original (T-5676: an alert named Åsa was stored as asa).
                last_word = start + len(want) - 1
                return text[spans[start][0]:spans[last_word][1]], last_word + 1
    return value, cursor


def _typed_words(typed_spans, spans) -> Dict[str, List[frozenset]]:
    """The folded words each listed typed span covers, by type.

    *typed_spans* holds ``(type, start, end)`` character spans of the query,
    read from the OVOS-INTENT-1 §5.6 typed-slot map; *spans* are the query's
    word spans from `_normalize_tokens`. Each listed span becomes the set of
    word indices it touches, so a slot value captured from the folded query
    can be compared with it.
    """
    words: Dict[str, List[frozenset]] = {}
    for type_name, start, end in typed_spans:
        covered = frozenset(i for i, (s, e) in enumerate(spans) if s < end and start < e)
        if covered:
            words.setdefault(type_name, []).append(covered)
    return words


def _shares_a_word(value, normed, listed) -> bool:
    """Whether *value* shares a word with one of the *listed* typed spans.

    *value* is a run of the folded query *normed*; every place it occurs is
    tried, since the matcher does not say which one it captured. A value that
    is no run of the query cannot be placed, and is not rejected for that.
    """
    want = str(value).split()
    located = False
    for start in range(len(normed) - len(want) + 1):
        if normed[start:start + len(want)] == want:
            located = True
            run = set(range(start, start + len(want)))
            if any(run & covered for covered in listed):
                return True
    return not located


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


#: Default upper bound on expanded samples retained per intent (and per
#: entity). Each expanded sample is resident for the process lifetime as a
#: regex string plus two matcher objects, so an unbounded bracket product in
#: one template can cost gigabytes across a real skill set.
#:
#: A phrasing dropped by this bound can NEVER match: the samples kept here
#: are the only regexes ``calc_intent`` ever tests against, and entity
#: values dropped here can never validate as that entity type. Measured
#: against ovos-skill-alerts' shipped templates, the old default of 2000
#: silently lost most of the coverage (de-DE matched 342/1000 phrasings at
#: 2000 vs 968/1000 at 200000; pt-PT matched 631/1000 vs 1000/1000), so the
#: default is set an order of magnitude higher, comfortably inside the
#: measured safe range. Pass ``max_expansions`` to :class:`IntentContainer`
#: to raise or lower it per deployment.
MAX_EXPANSIONS = 50000


def _fair_rations(totals: List[int], budget: int) -> List[int]:
    """How many expansions each line may keep, sharing ``budget`` as a POOL.

    A line that fits inside its share keeps ALL of its expansions and hands
    the remainder back to the lines that do not fit. So nothing is dropped
    while the intent TOTAL is inside the budget, whatever the shape of the
    individual lines, and when the total does exceed it the lines that
    overflow divide what the fitting lines left over.

    The rule was ``budget // len(lines)``: an equal ration whatever the file
    used in total. Two things followed from it, both measured on
    ovos-skill-weather en-US. A file at a ninth of the budget still truncated
    its one fat line -- 58 lines expanding to 5,593 in total, a ration of
    50000 // 58 = 862, and a line of 2,688 losing 1,826 phrasings that can
    never match. And ADDING a line LOWERED the ration of every other line, so
    the documented workaround, splitting the fat line, got tighter as a
    locale grew and could push a previously safe line over.

    This is the max-min fair share. Lines are served smallest first: each
    takes its whole total if that fits in an equal share of what is left, and
    otherwise takes that share. A line therefore never loses anything to a
    line that already fits.

    Args:
        totals: how many expansions each line produces, in line order.
        budget: the pool to divide, normally ``max_expansions``.

    Returns:
        One ration per line, in line order. Each is at least 1, so every
        template contributes a sample even when there are more lines than
        budget; that floor is the only case where the rations can add up to
        more than ``budget``.
    """
    rations = [0] * len(totals)
    remaining = budget
    unsatisfied = len(totals)
    for idx in sorted(range(len(totals)), key=lambda i: totals[i]):
        share = max(1, remaining // unsatisfied)
        rations[idx] = min(totals[idx], share)
        remaining = max(0, remaining - rations[idx])
        unsatisfied -= 1
    return rations


def _sample_within_budget(name: str, lines: List[str], budget: int):
    """Expand ``lines``, keeping at most ``budget`` samples across them all.

    Shared by :meth:`IntentContainer.add_intent` and
    :meth:`IntentContainer.add_entity` so the two cannot drift: the same
    accounting bug was written twice, and a fix applied to one would leave
    the other.

    A line that overflows its ration is sampled uniformly over its whole
    range (reservoir sampling, seeded deterministically by name and line
    index) rather than truncated at its first N, so a truncated line still
    contributes coverage from end to end.

    Args:
        name: the intent or entity name, used to seed the sampling.
        lines: the source templates.
        budget: the pool, normally ``max_expansions``.

    Returns:
        ``(samples, overflowed, grand_total)``. ``samples`` are the raw
        expansions, in line order, NOT normalized -- the intent path
        normalizes them and the entity path does not. ``overflowed`` holds
        ``(idx, line, total, ration)`` for each line that lost expansions.
    """
    totals = [sum(1 for _ in expand(line)) for line in lines]
    rations = _fair_rations(totals, budget)
    samples = []
    overflowed = []
    for idx, line in enumerate(lines):
        total, ration = totals[idx], rations[idx]
        if total <= ration:
            samples.extend(expand(line))
            continue
        rng = random.Random(f"{name}:{idx}")
        reservoir = []
        for i, e in enumerate(expand(line)):
            if i < ration:
                reservoir.append(e)
            else:
                j = rng.randint(0, i)
                if j < ration:
                    reservoir[j] = e
        samples.extend(reservoir)
        overflowed.append((idx, line, total, ration))
    return samples, overflowed, sum(totals)


class IntentContainer:
    def __init__(self, fuzz=False, n_workers=4, max_expansions=MAX_EXPANSIONS):
        self.intent_samples, self.entity_samples = {}, {}
        # each entity's values as the matcher folds a query, so a captured
        # value is compared in the form it was captured in
        self._folded_entities = {}
        # per-instance override of the module default MAX_EXPANSIONS, so a
        # deployment with a pathological template can lower the resident
        # memory cost (or raise it, if it has the budget) without touching
        # every other container in the process.
        self.max_expansions = max_expansions
        # OVOS-CONTEXT-1 §7 — per-intent set of declared template slot names,
        # parsed from the ``{slot}`` markers of the samples at registration.
        # Consumed by the pipeline to offer live context entries as slot
        # candidates for slots the utterance itself left unresolved.
        self.intent_slots = {}
        # OVOS-INTENT-1 §5.6 — per-intent ``slot -> type`` of the typed
        # placeholders. The template expansion strips ``{type:name}`` to
        # ``{name}``, so the pipeline records the types here.
        self.slot_types = {}
        # self.intents, self.entities = {}, {}
        self.fuzz = fuzz
        self.workers = n_workers
        self._cased_matchers = {}
        self._uncased_matchers = {}
        self.available_contexts = {}
        self.required_contexts = {}
        self.excluded_keywords = {}
        self.required_keywords = {}
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
        # of the process. The budget is spent as ONE POOL across the source
        # lines (see ``_fair_rations``): nothing is dropped while the intent
        # total fits, and a line that does overflow is sampled uniformly over
        # its whole range rather than truncated at its first N.
        budget = self.max_expansions
        raw, overflowed, grand_total = _sample_within_budget(name, lines, budget)
        expanded = [_normalize(e) for e in raw]
        if overflowed:
            dropped = sum(total - ration for _, _, total, ration in overflowed)
            details = "; ".join(
                f"line {idx} ({line[:40]!r}) expands to {total}, "
                f"{total - ration} phrasings dropped, {ration} kept"
                for idx, line, total, ration in overflowed
            )
            LOG.warning(f"intent {name!r} expands to {grand_total} samples, "
                        f"over max_expansions={budget}: {details}. {dropped} "
                        f"phrasings across this intent will NOT match any "
                        f"utterance (the lines that overflow share what the "
                        f"rest of the intent left unused, and each is sampled "
                        f"uniformly). Raise IntentContainer(max_expansions=...) "
                        f"if this intent needs to keep more.")
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
        # folded before the replacement test, because that test must read the
        # same spelling the store below uses: "Foo" replacing a stored "foo"
        # has to reach remove_entity, not only the assignment.
        name = name.lower()
        if name in self.entity_samples:
            LOG.debug(f"replacing existing entity: {name}")
            self.remove_entity(name)
        # same treatment as add_intent, through the same helper so the two
        # cannot drift: the budget is one pool across the source lines, and a
        # line that overflows is sampled uniformly rather than truncated at
        # its first N. A hard truncation here silently drops whichever values
        # expand last, and a value this entity never retains can never
        # validate a match against it (see the entity_samples membership
        # check in matches()).
        budget = self.max_expansions
        expanded, overflowed, grand_total = _sample_within_budget(
            name, lines, budget)
        if overflowed:
            dropped = sum(total - ration for _, _, total, ration in overflowed)
            details = "; ".join(
                f"line {idx} ({line[:40]!r}) expands to {total}, "
                f"{total - ration} values dropped, {ration} kept"
                for idx, line, total, ration in overflowed
            )
            LOG.warning(f"entity {name!r} expands to {grand_total} values, "
                        f"over max_expansions={budget}: {details}. {dropped} "
                        f"values across this entity will NEVER validate a "
                        f"match (the lines that overflow share what the rest "
                        f"of the entity left unused, and each is sampled "
                        f"uniformly). Raise IntentContainer(max_expansions=...) "
                        f"if this entity needs to keep more.")
        self.entity_samples[name] = set(expanded)
        self._folded_entities[name] = {_normalize(e) for e in expanded}
        self._cache_dirty = True  # Mark cache as needing rebuild

    def remove_entity(self, name: str):
        """
        Remove an entity
        @param name: name of entity to remove
        """
        name = name.lower()
        if name in self.entity_samples:
            del self.entity_samples[name]
            self._folded_entities.pop(name, None)

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
        query_words = set(query.split())

        def _kw_hit(kw):
            if ' ' not in kw:
                return kw in query_words
            return bool(re.search(r'\b' + re.escape(kw) + r'\b', query))

        for intent_name, samples in self.excluded_keywords.items():
            if any(_kw_hit(s) for s in samples):
                excluded_intents.append(intent_name)
        for intent_name, samples in self.required_keywords.items():
            if not any(_kw_hit(s) for s in samples):
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

    def _entity_key(self, intent_name: str, slot: str) -> Optional[str]:
        """The ``entity_samples`` key that holds slot *slot*'s value set.

        A template's slot name is bare (``{media_type}``), but the pipeline
        plugin registers a skill's ``.entity`` list under
        ``<skill_id>:<entity_name>``, because two skills may both declare a
        ``media_type`` and one must not answer for the other. So the bare slot
        name is looked up under the owning intent's namespace first, and only
        then as itself.

        The bare fallback is not legacy tolerance: a container used directly,
        without the plugin, registers entities under the plain name, and so
        does any caller that means one value set for every skill.

        The composed key is lowercased, because ``add_entity`` lowercases the
        name it stores under and ``add_intent`` does not. A skill id with an
        uppercase letter in it otherwise composes a key that no stored key can
        equal, and the slot reads as unregistered however the list was
        registered. The slot name needs no such repair: ``add_intent`` expands
        each sample through ``ovos_spec_tools.expansion.expand``, which refuses
        a slot name outside lowercase letters, digits and underscores, and
        ``_slot_names`` folds the name again to line up with the match keys. The
        fold on the bare candidate is therefore defence for a direct caller of
        this method, not a fix for a miss any template can reach.

        One limit: two skill ids that differ only in case compose a single key
        here, and ``add_entity`` already stores them as a single key, so this
        namespace separates skill ids that differ by more than case.

        Returns ``None`` when no value set is registered for the slot, which is
        the "unregistered" case the caller penalizes more lightly than a value
        that is registered and does not match.
        """
        if intent_name and ":" in intent_name:
            namespaced = f"{intent_name.split(':', 1)[0]}:{slot}".lower()
            if namespaced in self.entity_samples:
                return namespaced
        bare = slot.lower()
        if bare in self.entity_samples:
            return bare
        return None

    def _entity_member(self, k: str, value) -> bool:
        """Membership of ``value`` in entity ``k``'s samples, both folded.

        The match runs on the query as ``_normalize`` folds it: lowercase,
        diacritics and punctuation folded. A registered sample keeps the
        spelling the skill declared it with, so a plain ``in`` check judges
        "bob" no member of {"Bob"}, and "musica", the capture of "música", no
        member of {"música"}. Each miss costs the match the member score, and
        lets a live context candidate overwrite a value the user said
        (violates §7's "utterance value always wins" rule).
        """
        return _normalize(str(value)) in self._folded_entities[k]

    def _apply_slot_candidate(self, entities, k, v, slot_context, intent_name,
                              entity_key):
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
        if candidate is not None and self._entity_member(entity_key, candidate):
            entities[k] = candidate
            return True
        return False

    def _slot_penalty(self, intent_name, entities, slot_context, typed,
                      unregistered) -> Optional[float]:
        """The confidence penalty of the slots one regex bound, or ``None``
        when a typed slot binds words that no listed span of its type covers.

        OVOS-INTENT-1 §5.6 lets an engine require a span the typed-slot map
        lists for the slot's type, and a typed placeholder takes only a value
        of its type: "play jazz" is never a date. Where the map lists the
        type, a slot sharing no word with a listed span rejects the regex, and
        the pipeline narrows a slot that shares one to the listed span after
        the match. Where the map lists no span of the type, the parser may
        lack the language as well as the value, so the slot is left to the
        template.
        """
        normed, listed = typed
        types = self.slot_types.get(intent_name, {})
        penalty = 0.0
        for k, v in entities.items():
            spans = listed.get(types.get(k))
            if spans and not _shares_a_word(v, normed, spans):
                return None
            entity_key = self._entity_key(intent_name, k)
            if entity_key is None:
                # penalize unregistered entities
                penalty += unregistered
            elif not self._entity_member(entity_key, v):
                if self._apply_slot_candidate(entities, k, v, slot_context,
                                              intent_name, entity_key):
                    continue
                # penalize parsed entity value not in samples
                penalty += 0.1
        return penalty

    def _match(self, query, intent_name, regexes, slot_context=None, typed=None):
        typed = typed or (query.split(), {})
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
                slot_penalty = self._slot_penalty(intent_name, entities, slot_context,
                                                  typed, 0.04)
                if slot_penalty is None:
                    continue
                penalty += slot_penalty
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
                slot_penalty = self._slot_penalty(intent_name, entities, slot_context,
                                                  typed, entity_penalty)
                if slot_penalty is None:
                    continue
                if query_has_upper:
                    penalty += 0.05
                penalty += slot_penalty
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
                    if entities and self._slot_penalty(intent_name, entities["entities"],
                                                       None, typed, 0.0) is not None:
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

    def calc_intents(self, query: str, slot_context=None, typed_spans=()) -> Iterator[dict]:
        """
        Determine possible intents for a given query
        @param query: input to evaluate for an intent match
        @param slot_context: OVOS-CONTEXT-1 §7 — optional mapping of
            ``(owner_id, slot_name) -> value`` of live session context
            candidates, offered to the matcher before it resolves competing
            regex candidates
        @param typed_spans: OVOS-INTENT-1 §5.6 — ``(type, start, end)``
            character spans of *query* that the typed-slot map lists; a typed
            slot must bind words one of them covers
        @return: yields dict intent matches
        """
        utterance = query
        normed_tokens, word_spans = _normalize_tokens(utterance)
        query = " ".join(normed_tokens)
        typed = (normed_tokens, _typed_words(typed_spans, word_spans))

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
            res = self._match(query, intent_name, regexes, slot_context, typed)
            if res is not None:
                # OVOS-INTENT-1 §5.2/§5.3: the slot carries the surface words,
                # not the folded ones the match ran on
                entities = res.get("entities")
                if entities:
                    restored, cursor = {}, 0
                    for k, v in entities.items():
                        restored[k], cursor = _surface_value(
                            v, normed_tokens, word_spans, utterance, cursor)
                    res["entities"] = restored
                yield res

    def _tie_key(self, t: dict):
        """Order tied intent matches by pattern specificity, not by name.

        A literal (slot-free) pattern beats one with entities/wildcards; among
        those, the pattern capturing the smaller share of its tokens as slots
        is more specific and wins. The regex wildcard penalty and, only as a
        final deterministic fallback, the intent name break any remaining tie.
        Shared by ``calc_intent`` above and ``opm.py``'s pipeline-level
        tie-break so both paths resolve ties identically.
        """
        r = t.get("_matched_regex", "")
        is_literal = "{" not in r and "*" not in r
        tokens = r.split()
        slot_share = sum(1 for tok in tokens if "{" in tok or "*" in tok) / len(tokens) if tokens else 0.0
        return (
            0 if is_literal else 1,  # literal beats entity/wildcard
            slot_share,  # smaller share of slots = more specific pattern wins
            self._regex_penalty.get(r, 1.0),
            t["name"],  # deterministic final fallback only
        )

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
            ties.sort(key=self._tie_key)

        match = dict(ties[0])
        match.pop("_matched_regex", None)

        for entity in set(match["entities"].keys()):
            entities = match["entities"].pop(entity)
            match["entities"][entity.lower()] = entities
        LOG.debug(match)
        return match

    def exclude_keywords(self, intent_name, samples):
        folded = [kw for kw in map(_normalize, samples) if kw]
        self.excluded_keywords.setdefault(intent_name, []).extend(folded)
        self._cache_dirty = True  # Mark cache as needing rebuild

    def require_keywords(self, intent_name, samples):
        # an intent with no keyword left after folding has no requirement,
        # so an empty set must not be stored: it would reject every query
        folded = [kw for kw in map(_normalize, samples) if kw]
        if folded:
            self.required_keywords.setdefault(intent_name, []).extend(folded)
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
