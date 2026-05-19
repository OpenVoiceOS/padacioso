"""Domain-aware intent container for hierarchical intent organisation.

Mirrors the design shipped by :mod:`nebulento`, :mod:`ovos_padatious`, and
:mod:`palavreado`: intents are grouped into *domains*, a top-level
:class:`~padacioso.IntentContainer` first picks the domain, and the
domain's sub-container resolves the intent.

This typically reduces both intent-search cost (per-domain containers are
smaller) and the false-positive rate on out-of-domain utterances (the
top-level classifier rejects them before they reach any sub-container).
"""

from collections import defaultdict
from typing import Dict, List, Optional

from padacioso import IntentContainer


class DomainIntentContainer:
    """Two-level intent engine: domain classification followed by intent matching.

    Intents are grouped into *domains*. At query time the engine first
    selects the most likely domain via :attr:`domain_engine`, then runs the
    domain-specific container to find the best intent within that domain.

    Domains can also be selected explicitly, bypassing the top-level
    classifier.

    Example::

        from padacioso import DomainIntentContainer

        d = DomainIntentContainer()
        d.register_domain_intent("media", "play",
                                  ["play {song}", "put on {song}"])
        d.register_domain_intent("home", "lights_on",
                                  ["lights on", "turn on the lights"])

        # Teach the domain classifier with representative utterances per
        # domain.  Re-using the intent samples is usually sufficient.
        d.domain_engine.add_intent("media",
                                    ["play {song}", "put on {song}"])
        d.domain_engine.add_intent("home",
                                    ["lights on", "turn on the lights"])

        result = d.calc_intent("play some jazz")
        # result["name"] == "play"

    Args:
        fuzz: Forwarded to every :class:`IntentContainer` created
            internally.  When ``True`` partial matching is enabled.
        n_workers: Forwarded to every internal :class:`IntentContainer`.
    """

    def __init__(self, fuzz: bool = False, n_workers: int = 4) -> None:
        self.fuzz = fuzz
        self.n_workers = n_workers
        #: Top-level classifier that maps queries to a domain name.
        self.domain_engine: IntentContainer = IntentContainer(
            fuzz=fuzz, n_workers=n_workers
        )
        #: Per-domain intent containers, keyed by domain name.
        self.domains: Dict[str, IntentContainer] = {}
        #: Raw training samples accumulated per domain (for inspection /
        #: re-training).  Each value is a list of (intent_name, lines)
        #: tuples that were registered under that domain.
        self.training_data: Dict[str, List[tuple]] = defaultdict(list)

    # ── domain management ──────────────────────────────────────────────────

    def remove_domain(self, domain_name: str) -> None:
        """Remove a domain and all its intents and training data."""
        self.training_data.pop(domain_name, None)
        self.domains.pop(domain_name, None)
        try:
            self.domain_engine.remove_intent(domain_name)
        except Exception:
            pass

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
        self.domains[domain_name].add_intent(intent_name, lines)
        self.training_data[domain_name].append((intent_name, list(lines)))

    def remove_domain_intent(self, domain_name: str, intent_name: str) -> None:
        """Remove an intent from a domain."""
        if domain_name in self.domains:
            self.domains[domain_name].remove_intent(intent_name)

    # ── query API ──────────────────────────────────────────────────────────

    def calc_domain(self, query: str) -> Optional[dict]:
        """Return the best matching domain match dict, or ``None``."""
        return self.domain_engine.calc_intent(query)

    def calc_intent(self, query: str,
                     domain: Optional[str] = None) -> Optional[dict]:
        """Return the best intent match for *query*.

        Args:
            query: The utterance to match.
            domain: If given, skip the top-level classifier and resolve the
                intent inside this domain directly.

        Returns:
            The match dict from the resolved domain's container, ``None``
            if no domain matched.
        """
        resolved_domain: Optional[str] = domain
        if resolved_domain is None:
            top = self.domain_engine.calc_intent(query)
            resolved_domain = top.get("name") if top else None
        if resolved_domain and resolved_domain in self.domains:
            return self.domains[resolved_domain].calc_intent(query)
        return None
