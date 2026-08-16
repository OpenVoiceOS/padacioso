# Pre-release quirks

Behavior changes since the last stable release, newest first. This file is
reset at each stable release.

## 2.2.4a1

- Wire registration is replace-on-reregister (OVOS-INTENT-4 §8.1) on the
  legacy `padatious:register_intent` / `padatious:register_entity` contracts
  too, matching the spec handlers. The dual-emit from ovos-workshop could
  previously land in an order that tripped the engine's strict
  re-registration guard, crashing entity registration at skill load
  ("Attempted to re-register existing entity") on a default install.
  Re-registration now replaces the prior entry (last wins) instead of
  raising or being ignored.
