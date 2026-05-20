# Domain Padacioso Pipeline

This page documents two layers that ship together:

* **`DomainPadaciosoPipeline`** — the OPM-discoverable pipeline class. Entry point: `ovos-padacioso-domain-pipeline`. Subclasses the flat `PadaciosoPipeline`; the only differences are the container shape (below) and that intents are routed to a domain == `skill_id` at registration time.
* **`DomainIntentContainer`** — the hierarchical, two-level variant of `IntentContainer` used internally by that pipeline.

A separate entry point (rather than a `domain_engine: true` config flag on the flat pipeline) keeps the two pipelines independently selectable in `default_pipeline` ordering and lets each have its own `intents.<key>` config block.

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

## Hierarchical container

`DomainIntentContainer` is the hierarchical variant of `IntentContainer`. Intents are grouped into *domains*, and at inference time the engine first picks the most likely domain via the top-level classifier, then resolves the intent inside that domain only. This mirrors the API shipped by sibling OVOS intent plugins (`nebulento.DomainIntentContainer`, `ovos_padatious.DomainIntentContainer`, `palavreado.DomainIntentContainer`, `ovos_m2v_pipeline.DomainPrototypeIntentStore`).

## Why hierarchical

Two-level matching gives two concrete benefits:

1. **Smaller per-domain containers** — per-query work scales with the size of the matched domain rather than the total intent count.
2. **Lower far-OOD false-positive rate** — the top-level router rejects chitchat that doesn't strongly match any domain *before* any sub-container is scanned.

## Routing

Padatious intents follow the convention `<skill_id>:<intent_name>`. The domain pipeline extracts the `skill_id` prefix from each registered intent label and uses it as the domain name. Labels without a `:` use the whole name as the domain (graceful fallback).

```
              utterance
                 │
                 ▼
        ┌──────────────────┐
        │  domain_engine   │  IntentContainer (router)
        └──────────────────┘
                 │
            best domain
                 │
                 ▼
        ┌──────────────────┐
        │ domains[<name>]  │  IntentContainer (per-domain intents)
        └──────────────────┘
                 │
           PadaciosoIntent
```

Every `padatious:register_intent` does two things:

* Adds the templates to the domain's `IntentContainer` (`domains[skill_id]`) under the full `skill_id:intent` label.
* Seeds the same templates under the domain name in the top-level `domain_engine`; the router learns the domain's surface forms incrementally.

Entities are shared across domains: a `padatious:register_entity` adds the entity to every sub-container and to the router.

`detach_intent` removes only the named intent from its domain; if the domain is left empty, the domain entry is dropped from the router as well. `detach_skill` removes the whole domain in one shot.

## Programmatic usage

```python
from padacioso import DomainIntentContainer

d = DomainIntentContainer()
d.register_domain_intent("media", "play",
                          ["play {song}", "put on {song}"])
d.register_domain_intent("home", "lights_on",
                          ["lights on", "turn on the lights"])

# Seed the router with representative utterances per domain.
d.domain_engine.add_intent("media",
                            ["play {song}", "put on {song}"])
d.domain_engine.add_intent("home",
                            ["lights on", "turn on the lights"])

d.calc_intent("play some jazz")
# {'name': 'play', ..., 'conf': 0.85}
```

### Bypassing the router

Pass `domain=...` to `calc_intent` to skip the top-level classifier and resolve directly inside a specific domain — useful for session/context-driven scoping where the caller already knows the active domain:

```python
d.calc_intent("play some jazz", domain="media")
```

## See also

- [Padacioso README](../README.md) — flat pipeline overview and template syntax.
