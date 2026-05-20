# Domain Padacioso Pipeline

This page documents two layers that ship together:

* **`DomainPadaciosoPipeline`** — the OPM-discoverable pipeline class. Entry point: `ovos-padacioso-domain-pipeline`. Subclasses the flat `PadaciosoPipeline`; the only differences are the container shape (below) and that intents are routed to a domain == `skill_id` at registration time.
* **`DomainIntentContainer`** — the parallel-argmax variant of `IntentContainer` used internally by that pipeline.

A separate entry point (rather than a config flag on the flat pipeline) keeps the two pipelines independently selectable in `default_pipeline` ordering and lets each have its own `intents.<key>` config block.

## Enabling

Add it to your OVOS config and place it in your pipeline order alongside (or in place of) the flat plugin:

```json
{
  "intents": {
    "ovos-padacioso-domain-pipeline": {
      "fuzz": true
    },
    "pipeline": [
      "ovos-padacioso-domain-pipeline-high",
      "ovos-padacioso-domain-pipeline-medium",
      "ovos-padacioso-domain-pipeline-low"
    ]
  }
}
```

Configuration keys are read from `intents.ovos_padacioso_domain_pipeline`. The pipeline accepts every key the flat plugin does (`fuzz`, `workers`, `conf_high`, `conf_med`, `conf_low`).

## Domain container

`DomainIntentContainer` groups intents into *domains* (one sub-container per domain) and evaluates every domain in parallel at inference time, returning the global argmax. This mirrors the parallel-argmax pattern shipped by sibling OVOS intent engines (adapt, `nebulento.DomainIntentContainer`, `ovos_padatious.DomainIntentContainer`, `palavreado.DomainIntentContainer`, `ovos_m2v_pipeline.DomainPrototypeIntentStore`).

There is intentionally no top-level "router" container. Strict regex matching is the wrong tool for routing: paraphrases that don't match any router template would block the sub-stage from ever running, even when a domain has a perfect template hit. Parallel evaluation is strictly more permissive and — for padacioso — practically free.

## Why grouped by domain

Two concrete benefits over a flat container:

1. **Targeted scoping** — `calc_intent(query, domain=...)` evaluates a single sub-container, useful for session/context-driven scoping where the caller already knows the active domain.
2. **Cheap prefilter** — domains whose templates share zero literal tokens with the utterance are skipped before any regex runs.
3. **Short-circuit on decisive match** — padacioso hits literal templates at 0.95 confidence; the first such hit ends the scan.

## Routing

Padatious intents follow the convention `<skill_id>:<intent_name>`. The domain pipeline extracts the `skill_id` prefix from each registered intent label and uses it as the domain name. Labels without a `:` use the whole name as the domain (graceful fallback).

```
              utterance
                 │
                 ▼
   ┌─────────────────────────────────┐
   │  prefilter by literal tokens    │
   └─────────────────────────────────┘
                 │
       candidate domains
                 │
                 ▼
   ┌─────────────────────────────────┐
   │ domains[d1].calc_intent(query)  │
   │ domains[d2].calc_intent(query)  │  parallel argmax
   │ domains[d3].calc_intent(query)  │
   └─────────────────────────────────┘
                 │
        best by confidence
                 │
                 ▼
           PadaciosoIntent
```

Every `padatious:register_intent` adds the templates to the domain's `IntentContainer` (`domains[skill_id]`) under the full `skill_id:intent` label.

Entities are shared across domains: a `padatious:register_entity` adds the entity to every sub-container.

`detach_intent` removes only the named intent from its domain; if the domain is left empty, the domain entry is dropped. `detach_skill` removes the whole domain in one shot.

## Programmatic usage

```python
from padacioso import DomainIntentContainer

d = DomainIntentContainer()
d.register_domain_intent("media", "play",
                          ["play {song}", "put on {song}"])
d.register_domain_intent("home", "lights_on",
                          ["lights on", "turn on the lights"])

d.calc_intent("play some jazz")
# {'name': 'play', ..., 'conf': 0.95}
```

### Scoping to a single domain

Pass `domain=...` to `calc_intent` to evaluate only that domain — useful for session/context-driven scoping where the caller already knows the active domain:

```python
d.calc_intent("play some jazz", domain="media")
```

### Top-K matches

```python
d.calc_intents("play some jazz", top_k=3)
# [{'name': 'play', 'conf': 0.95, ...}, ...]
```

## See also

- [Padacioso README](../README.md) — flat pipeline overview and template syntax.
