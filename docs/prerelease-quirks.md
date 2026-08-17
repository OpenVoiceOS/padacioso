# Pre-release quirks

Behavior changes since the last stable release, newest first. This file is
reset at each stable release.

## 2.2.6a1

- Expanded samples are bounded: an intent retains at most 2000 expanded
  samples (budget spread across its template lines) and an entity at most
  2000 expanded values. Every expanded sample is resident for the process
  lifetime as a regex string plus two matcher objects, so unbounded bracket
  products in one template could cost gigabytes across a real skill set.
  Templates expanding past the bound log a warning naming the intent.

## 2.2.5a1

- Engine-level `add_intent`/`add_entity` are last-write-wins: re-adding an
  existing name replaces it instead of raising. Wire registrations race on
  thread-pooled handlers (the dual-emit's two frames), so the strict guard
  crashed skill loading nondeterministically — worst under slow or
  memory-starved boots. Code relying on the `RuntimeError` to detect
  duplicates must check `name in container.intent_samples` first.

## 2.2.4a1

- Wire registration is replace-on-reregister (OVOS-INTENT-4 §8.1) on the
  legacy `padatious:register_intent` / `padatious:register_entity` contracts
  too, matching the spec handlers. The dual-emit from ovos-workshop could
  previously land in an order that tripped the engine's strict
  re-registration guard, crashing entity registration at skill load
  ("Attempted to re-register existing entity") on a default install.
  Re-registration now replaces the prior entry (last wins) instead of
  raising or being ignored.
