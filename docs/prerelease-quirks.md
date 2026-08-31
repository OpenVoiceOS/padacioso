# Pre-release quirks

Behavior changes since the last stable release, newest first. This file is
reset at each stable release.

## 2.3.0a1

- OVOS-CONTEXT-1 §7 uniform slot fill: a declared template slot (`{slot}`)
  the utterance leaves unresolved is filled from a live, non-null
  `session.intent_context` entry (private `<skill_id>:name` taking
  precedence over a shared bare `name`), independently of
  `requires_context`/`excludes_context`. A value the utterance itself
  produces for the slot is never overwritten. For an entity-typed slot the
  utterance DID bind, but to a value outside the registered entity's value
  set, the context candidate is offered to the matcher before the
  membership check that would otherwise apply padacioso's confidence
  penalty — so the value participates in intent selection cleanly instead
  of losing to a competing intent on a penalized score.
- OVOS-INTENT-2 §4.3 per-slot value blacklist: a template registration may
  carry a `slot_blacklist` mapping (or a dict-typed `blacklist`, disambiguated
  from the list-typed §6.1 intent-suppression `blacklist`) of
  slot name -> values that must never bind that slot. A bound value matching
  the blacklist by WHOLE-VALUE equality (lowercased word-list comparison,
  matching ovos-padatious-pipeline-plugin) is treated as unresolved, making
  it eligible for the §7 context fill above. A multi-word value that merely
  contains a blacklisted word ("the it crowd" against a blacklist of `it`)
  is a legitimate binding and is left untouched.
- The §7 pre-match entity-membership check is case-insensitive: a registered
  entity sample keeps whatever case the skill declared it with, but the
  query is lowercased before matching, so a case-differing but otherwise
  correct utterance-produced value (`"bob"` against an entity value
  `"Bob"`) is recognized as a valid member and is never treated as
  unresolved (which would otherwise let a live context candidate silently
  overwrite it).

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
