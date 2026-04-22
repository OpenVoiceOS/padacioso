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

Measured on a 269-utterance labelled dataset (244 match cases across 22 intents, 25 deliberate no-match cases).
Run `python benchmark/accuracy.py` to reproduce.

| Mode | Accuracy | Precision | Recall | F1 | False positives |
|---|---|---|---|---|---|
| `fuzz=False` | **97.8%** | **100%** | 97.5% | 0.988 | 0 / 25 (0%) |
| `fuzz=True` | 97.0% | 98.4% | **98.4%** | 0.984 | 4 / 25 (16%) |

`fuzz=False` achieves perfect precision (zero false positives) at the cost of missing a small
number of paraphrases not covered by training templates. `fuzz=True` recovers most of those but
introduces false positives on clearly unrelated utterances due to loose similarity scoring.

The remaining 6 non-fuzz misses are genuine template gaps (e.g. `"play the next song"` matching
`play_music` instead of `next_track`, `"i need help"` captured by `add_shopping`) — fixable by
adding one training line each.

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
