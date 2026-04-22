# Padacioso

A lightweight, dependency-light intent parser for [OpenVoiceOS](https://openvoiceos.org), compatible with the Padatious intent file format.

## Features

- `(one|of|these)` alternation and `[optional]` syntax
- `{entity}` capture groups with optional type annotations (`:int`, `:float`, `:word`)
- Fuzzy matching fallback
- Context gating and keyword exclusion
- Symmetric normalization — apostrophe variants and extra whitespace are handled identically in training data and at query time

## Install

```bash
pip install padacioso
```

## Quick start

```python
from padacioso import IntentContainer

container = IntentContainer()
container.add_intent("play", ["play {song}", "play some {song}", "put on {song}"])
container.add_intent("weather", ["what is the weather [today]", "weather forecast"])
container.add_entity("song", ["bohemian rhapsody", "stairway to heaven"])

result = container.calc_intent("play bohemian rhapsody")
# {'name': 'play', 'entities': {'song': 'bohemian rhapsody'}, 'conf': 1.0}
```

### Confidence scoring

| Situation | Confidence |
|---|---|
| Exact, cased match, registered entity value | 1.00 |
| Exact match, entity value not in samples | 0.90 |
| Exact match, unregistered entity | 0.96 |
| Case-insensitive match | −0.05 |
| Wildcard (`*`) — proportional to open-token ratio | −0.05 … −0.25 |

### Fuzzy matching

```python
container = IntentContainer(fuzz=True)
```

Enables approximate matching for utterances that are close but not exact.

### Context gating

```python
container.require_context("purchase", "authenticated")
container.set_context("purchase", "authenticated")
container.exclude_keywords("music", ["stop"])
```

## Accuracy

Run `python benchmark/accuracy.py` to reproduce. 268 test cases: 244 labelled match utterances across 22 intents, 24 deliberate no-match cases.

### Template coverage (utterances close to training patterns)

When test utterances are paraphrases that stay close to the training templates:

| Mode | Accuracy | Precision | Recall | F1 | False positives |
|---|---|---|---|---|---|
| `fuzz=False` | **98.5%** | **100%** | 98.4% | 0.992 | 0 / 24 |
| `fuzz=True` | 97.8% | 98.4% | 99.2% | 0.988 | 4 / 24 |

### Natural language recall (real human utterances)

When test utterances are genuinely natural — contractions, idioms, indirect phrasing, British
colloquialisms — the benchmark uses the same training templates unchanged:

| Mode | Accuracy | Precision | Recall | F1 | False positives |
|---|---|---|---|---|---|
| `fuzz=False` | 30% | **100%** | 23% | 0.38 | 0 / 24 |
| `fuzz=True` | 51% | 97% | 48% | 0.64 | 4 / 24 |

This is expected and by design. Padacioso is a **pattern matcher**, not an NLU engine. It matches
exactly what its training templates cover. For `"it's dark in here"` to trigger `lights_on`, the
skill author must add that phrasing (or a generalisation of it) to the intent file. This gives
deterministic, auditable behaviour at the cost of requiring broader training coverage.

The natural-language dataset is included (`benchmark/dataset.py`) to make this tradeoff visible
and to help skill authors understand which phrasings need explicit template coverage.

### Engine comparison (natural language, same dataset)

Run `uv run python benchmark/compare.py` to reproduce. All engines use identical training templates
and are evaluated on the same 268 natural-language cases.

| Engine | Accuracy | Precision | Recall | F1 | False positives | Query latency |
|---|---|---|---|---|---|---|
| padaos (regex) | 25.4% | **100%** | 18.0% | 0.306 | 0 / 24 | 0.10 ms |
| padacioso `fuzz=False` | 30.2% | **100%** | 23.4% | 0.379 | 0 / 24 | **0.17 ms** |
| padacioso `fuzz=True` | **51.1%** | 96.7% | **48.0%** | **0.641** | 4 / 24 | 26.9 ms |
| padatious (neural) | 48.9% | 95.7% | 45.9% | 0.620 | 5 / 24 | 0.79 ms |
| rapidfuzz token_set_ratio | 42.9% | 94.2% | 39.8% | 0.559 | 6 / 24 | 0.44 ms |

padaos and padacioso `fuzz=False` are the most precise (zero false positives) but only match
utterances that closely follow the training templates. `fuzz=True` reaches the same recall
as the neural padatious at lower latency on cache-warm queries, but costs ~27 ms per query.
For production use, `fuzz=False` is recommended; add `fuzz=True` only when recall on
natural phrasing matters more than latency.

## Performance

Benchmarks on a mid-range laptop (single thread, Python 3.11, 500 iterations):

| Scenario | Median | p95 |
|---|---|---|
| Register 20 intents | 2.7 ms | 3.2 ms |
| Query — exact match (20 intents) | 0.46 ms | 0.72 ms |
| Query — entity match (20 intents) | 0.48 ms | 0.69 ms |
| Query — no match (20 intents) | 0.48 ms | 0.73 ms |
| Query — exact match (100 intents) | 0.61 ms | 0.84 ms |
| Query — exact match (500 intents) | 1.05 ms | 1.39 ms |
| Query — exact match (10 000 intents) | 13.8 ms | 16.2 ms |
| Query — no match (10 000 intents) | 31.0 ms | 33.4 ms |

Matched queries short-circuit at 0.95 confidence, so they scan only a fraction of the intent list.
No-match queries must exhaust every intent; above ~1 000 intents a pre-filter (BM25 or token-set) would help.

### Fuzzy vs non-fuzzy (20 intents)

| Query type | `fuzz=False` | `fuzz=True` | Overhead |
|---|---|---|---|
| Exact match | 0.57 ms | 2.9 ms | ~5× |
| Entity match | 0.46 ms | 0.6 ms | ~1.3× |
| Near miss | 0.42 ms | 8.3 ms | ~20× |
| No match | 0.42 ms | 0.8 ms | ~2× |

Fuzz variants are pre-computed at registration time. Two runtime gates keep per-query work low:
a **word-count filter** skips patterns whose length differs too much from the query, and a
**token-overlap filter** skips patterns that share no literal words with the query at all.
Entity matches and no-match cases benefit most; near-miss queries (partial word overlap) still
pay the full similarity cost. Prefer `fuzz=False` (the default) for production deployments.

## OVOS plugin

Padacioso ships as an OVOS pipeline plugin (`ovos-padacioso-pipeline-plugin`) and is a drop-in replacement for Padatious when loaded via the plugin manager.

```yaml
# ~/.config/mycroft/mycroft.conf
intents:
  pipeline:
    - ovos-padacioso-pipeline-plugin-high
    - ovos-padacioso-pipeline-plugin-medium
    - ovos-padacioso-pipeline-plugin-low
```

## License

Apache 2.0
