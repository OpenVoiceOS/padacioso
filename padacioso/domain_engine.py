"""Domain-aware intent container for hierarchical intent organisation.

Mirrors the parallel-argmax design used by sibling intent engines
(adapt, nebulento, ovos_padatious, palavreado): intents are grouped into
*domains*, and at query time **every** domain's sub-container is
evaluated in parallel; the global best confidence wins.

There is intentionally no top-level "router" container. Strict regex
matching (padacioso) is the wrong tool for routing: paraphrases that
don't match any router template would block the sub-stage from ever
running, even when a domain sub-container has a perfect template hit.
Parallel evaluation is strictly more permissive and, for padacioso,
practically free (regex matching is fast and we additionally prefilter
domains by literal-token overlap and short-circuit on the first 0.95
hit).
"""

import re
from typing import Dict, List, Optional, Set

from padacioso import IntentContainer, _normalize as normalize_example


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _literal_tokens(line: str) -> Set[str]:
    """Return the set of literal word tokens in a padacioso template line.

    Entity placeholders (``{name}``), wildcards (``*``) and bracketed
    alternations are stripped so only fixed surface tokens remain.
    """
    try:
        text = normalize_example(line)
    except Exception:
        text = line
    # Drop entity placeholders
    text = re.sub(r"\{[^}]*\}", " ", text)
    # Drop bracket-alternation syntax (kept tokens are still extracted by regex)
    text = text.replace("(", " ").replace(")", " ").replace("|", " ")
    text = text.replace("*", " ")
    return {t.lower() for t in _TOKEN_RE.findall(text)}


class DomainIntentContainer:
    """Parallel-argmax intent engine across per-domain sub-containers.

    Intents are grouped into *domains*. At query time the engine asks
    every sub-container to match and returns the global best.

    Example::

        from padacioso import DomainIntentContainer

        d = DomainIntentContainer()
        d.register_domain_intent("media", "play",
                                  ["play {song}", "put on {song}"])
        d.register_domain_intent("home", "lights_on",
                                  ["lights on", "turn on the lights"])

        result = d.calc_intent("play some jazz")
        # result["name"] == "play"

    Args:
        fuzz: Forwarded to every :class:`IntentContainer` created
            internally.  When ``True`` partial matching is enabled.
        n_workers: Forwarded to every internal :class:`IntentContainer`.
    """

    #: Confidence at/above which the first matching domain short-circuits.
    _GOOD_ENOUGH = 0.95

    def __init__(self, fuzz: bool = False, n_workers: int = 4) -> None:
        self.fuzz = fuzz
        self.n_workers = n_workers
        #: Per-domain intent containers, keyed by domain name.
        self.domains: Dict[str, IntentContainer] = {}
        #: Literal-token vocabulary per domain (for cheap prefilter).
        self._domain_vocab: Dict[str, Set[str]] = {}

    # ── domain management ──────────────────────────────────────────────────

    def remove_domain(self, domain_name: str) -> None:
        """Remove a domain and all its intents."""
        self.domains.pop(domain_name, None)
        self._domain_vocab.pop(domain_name, None)

    # ── intent management ──────────────────────────────────────────────────

    def register_domain_intent(self, domain_name: str, intent_name: str,
                                lines: List[str]) -> None:
        """Register an intent inside a domain.

        Creates the domain's :class:`IntentContainer` on first use.

        Args:
            domain_name: Target domain (created if it does not exist).
            intent_name: Unique intent name within the domain.
            lines: Padacioso template lines for the intent.
        """
        if domain_name not in self.domains:
            self.domains[domain_name] = IntentContainer(
                fuzz=self.fuzz, n_workers=self.n_workers
            )
            self._domain_vocab[domain_name] = set()
        self.domains[domain_name].add_intent(intent_name, lines)
        for line in lines:
            self._domain_vocab[domain_name] |= _literal_tokens(line)

    def remove_domain_intent(self, domain_name: str, intent_name: str) -> None:
        """Remove an intent from a domain."""
        if domain_name in self.domains:
            self.domains[domain_name].remove_intent(intent_name)
            # Vocabulary is not pruned per-intent (cheap over-approximation
            # only widens the prefilter; correctness is preserved).

    # ── query API ──────────────────────────────────────────────────────────

    def _candidate_domains(self, query: str) -> List[str]:
        """Cheap literal-token prefilter: keep domains whose vocab overlaps."""
        utt_tokens = {t.lower() for t in _TOKEN_RE.findall(query)}
        if not utt_tokens:
            return list(self.domains.keys())
        candidates = []
        for name, vocab in self._domain_vocab.items():
            # Empty vocab (only entity/wildcard templates) -> can't prefilter.
            if not vocab or utt_tokens & vocab:
                candidates.append(name)
        return candidates

    def calc_intent(self, query: str,
                     domain: Optional[str] = None) -> Optional[dict]:
        """Return the global best intent match for *query*.

        Args:
            query: The utterance to match.
            domain: If given, evaluate only inside this domain.

        Returns:
            The match dict from the winning domain's container, or ``None``.
        """
        if domain is not None:
            sub = self.domains.get(domain)
            return sub.calc_intent(query) if sub is not None else None

        best: Optional[dict] = None
        best_conf = 0.0
        for name in self._candidate_domains(query):
            sub = self.domains[name]
            match = sub.calc_intent(query)
            if not match or not match.get("name"):
                continue
            conf = match.get("conf", 0) or 0
            if conf > best_conf:
                best = match
                best_conf = conf
                # padacioso hits literal templates at 0.95; first such match
                # is decisive enough to skip remaining domains.
                if best_conf >= self._GOOD_ENOUGH:
                    break
        return best

    def calc_intents(self, query: str, top_k: int = 5) -> List[dict]:
        """Return the top-K intent matches across all domains.

        Each sub-container contributes its best match; results are sorted
        by confidence descending and truncated to ``top_k``.
        """
        results: List[dict] = []
        for name in self._candidate_domains(query):
            sub = self.domains[name]
            for match in sub.calc_intents(query):
                if match and match.get("name"):
                    results.append(match)
        results.sort(key=lambda m: m.get("conf", 0) or 0, reverse=True)
        return results[:top_k]
