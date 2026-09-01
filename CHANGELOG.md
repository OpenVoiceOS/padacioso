# Changelog

## [2.3.1a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.1a1) (2026-09-01)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.0a1...2.3.1a1)

**Merged pull requests:**

- fix: warn and sample uniformly when the intent sample cap truncates a line [\#88](https://github.com/OpenVoiceOS/padacioso/pull/88) ([JarbasAl](https://github.com/JarbasAl))

## [2.3.0a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.0a1) (2026-08-31)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.6a1...2.3.0a1)

**Merged pull requests:**

- feat: CONTEXT-1 §7 uniform slot fill + INTENT-2 §4.3 slot blacklist [\#69](https://github.com/OpenVoiceOS/padacioso/pull/69) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.6a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.6a1) (2026-08-17)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.5a2...2.2.6a1)

**Merged pull requests:**

- fix: bound expanded samples retained per intent and entity [\#85](https://github.com/OpenVoiceOS/padacioso/pull/85) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.5a2](https://github.com/OpenVoiceOS/padacioso/tree/2.2.5a2) (2026-08-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.5a1...2.2.5a2)

**Merged pull requests:**

- docs: prerelease-quirks entry for last-write-wins registration [\#83](https://github.com/OpenVoiceOS/padacioso/pull/83) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.5a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.5a1) (2026-08-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.4a1...2.2.5a1)

**Merged pull requests:**

- fix: engine add is last-write-wins, never raises on re-registration [\#81](https://github.com/OpenVoiceOS/padacioso/pull/81) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.4a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.4a1) (2026-08-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.3a1...2.2.4a1)

**Merged pull requests:**

- fix: replace-on-reregister on the legacy wire contracts [\#79](https://github.com/OpenVoiceOS/padacioso/pull/79) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.3a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.3a1) (2026-08-10)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.2a2...2.2.3a1)

**Merged pull requests:**

- fix: scope intent detach to the target language [\#77](https://github.com/OpenVoiceOS/padacioso/pull/77) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.2a2](https://github.com/OpenVoiceOS/padacioso/tree/2.2.2a2) (2026-08-01)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.2a1...2.2.2a2)

**Merged pull requests:**

- docs: rewrite README in Simplified Technical English [\#75](https://github.com/OpenVoiceOS/padacioso/pull/75) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.2a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.2a1) (2026-07-26)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.1a1...2.2.2a1)

**Merged pull requests:**

- fix: session blacklist bypassed by the legacy/INTENT-4 intent-name alias [\#73](https://github.com/OpenVoiceOS/padacioso/pull/73) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.1a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.1a1) (2026-07-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.2.0a1...2.2.1a1)

**Merged pull requests:**

- fix: skip malformed template samples instead of crashing registration [\#70](https://github.com/OpenVoiceOS/padacioso/pull/70) ([JarbasAl](https://github.com/JarbasAl))

## [2.2.0a1](https://github.com/OpenVoiceOS/padacioso/tree/2.2.0a1) (2026-07-02)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.1.2a1...2.2.0a1)

**Merged pull requests:**

- feat: enforce OVOS-CONTEXT-1 requires\_context/excludes\_context gating [\#67](https://github.com/OpenVoiceOS/padacioso/pull/67) ([JarbasAl](https://github.com/JarbasAl))

## [2.1.2a1](https://github.com/OpenVoiceOS/padacioso/tree/2.1.2a1) (2026-07-02)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.1.1a1...2.1.2a1)

**Merged pull requests:**

- fix: re-arm legacy-registered intents on ovos.intent.enable \(§8.5\) [\#65](https://github.com/OpenVoiceOS/padacioso/pull/65) ([JarbasAl](https://github.com/JarbasAl))

## [2.1.1a1](https://github.com/OpenVoiceOS/padacioso/tree/2.1.1a1) (2026-06-28)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.1.0a1...2.1.1a1)

**Merged pull requests:**

- fix: lift ovos-spec-tools upper bound \(spec-tools 1.x\) [\#63](https://github.com/OpenVoiceOS/padacioso/pull/63) ([JarbasAl](https://github.com/JarbasAl))

## [2.1.0a1](https://github.com/OpenVoiceOS/padacioso/tree/2.1.0a1) (2026-06-28)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.0.1a1...2.1.0a1)

**Merged pull requests:**

- feat: consume OVOS-INTENT-4 template registration \(alongside legacy\) [\#59](https://github.com/OpenVoiceOS/padacioso/pull/59) ([JarbasAl](https://github.com/JarbasAl))

## [2.0.1a1](https://github.com/OpenVoiceOS/padacioso/tree/2.0.1a1) (2026-06-27)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.0.0a1...2.0.1a1)

**Merged pull requests:**

- fix: drop unhashable Session from lru\_cache key \(ovos-bus-client 2.x compat\) [\#60](https://github.com/OpenVoiceOS/padacioso/pull/60) ([JarbasAl](https://github.com/JarbasAl))

## [2.0.0a1](https://github.com/OpenVoiceOS/padacioso/tree/2.0.0a1) (2026-06-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.1.1a1...2.0.0a1)

**Breaking changes:**

- feat!: enforce OVOS-INTENT-1 grammar and normalization via ovos-spec-tools [\#55](https://github.com/OpenVoiceOS/padacioso/pull/55) ([JarbasAl](https://github.com/JarbasAl))

## [1.1.1a1](https://github.com/OpenVoiceOS/padacioso/tree/1.1.1a1) (2026-06-06)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.1.0a1...1.1.1a1)

**Merged pull requests:**

- fix\(deps\): allow ovos-bus-client 2.x \(widen cap to \<3.0.0\) [\#56](https://github.com/OpenVoiceOS/padacioso/pull/56) ([JarbasAl](https://github.com/JarbasAl))

## [1.1.0a1](https://github.com/OpenVoiceOS/padacioso/tree/1.1.0a1) (2026-05-14)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.2a3...1.1.0a1)

**Merged pull requests:**

- feat\(test\): ovoscope end-to-end tests for PadaciosoPipeline [\#51](https://github.com/OpenVoiceOS/padacioso/pull/51) ([JarbasAl](https://github.com/JarbasAl))

## [1.0.2a3](https://github.com/OpenVoiceOS/padacioso/tree/1.0.2a3) (2026-04-22)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.2a2...1.0.2a3)

**Merged pull requests:**

- perf/fix: accuracy and speed improvements [\#49](https://github.com/OpenVoiceOS/padacioso/pull/49) ([JarbasAl](https://github.com/JarbasAl))

## [1.0.2a2](https://github.com/OpenVoiceOS/padacioso/tree/1.0.2a2) (2026-04-21)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.2a1...1.0.2a2)

**Merged pull requests:**

- Update dependency ovos-bus-client to v1 [\#45](https://github.com/OpenVoiceOS/padacioso/pull/45) ([renovate[bot]](https://github.com/apps/renovate))

## [1.0.2a1](https://github.com/OpenVoiceOS/padacioso/tree/1.0.2a1) (2026-04-21)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.1a4...1.0.2a1)

**Merged pull requests:**

- fix: normalize whitespace and apostrophes for training data and inference queries [\#44](https://github.com/OpenVoiceOS/padacioso/pull/44) ([JarbasAl](https://github.com/JarbasAl))

## [1.0.1a4](https://github.com/OpenVoiceOS/padacioso/tree/1.0.1a4) (2025-12-19)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.1a3...1.0.1a4)

**Merged pull requests:**

- chore\(deps\): update dependency python to 3.14 [\#37](https://github.com/OpenVoiceOS/padacioso/pull/37) ([renovate[bot]](https://github.com/apps/renovate))

## [1.0.1a3](https://github.com/OpenVoiceOS/padacioso/tree/1.0.1a3) (2025-12-18)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.1a2...1.0.1a3)

**Merged pull requests:**

- chore: Configure Renovate [\#36](https://github.com/OpenVoiceOS/padacioso/pull/36) ([renovate[bot]](https://github.com/apps/renovate))

## [1.0.1a2](https://github.com/OpenVoiceOS/padacioso/tree/1.0.1a2) (2025-11-10)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.1a1...1.0.1a2)

**Merged pull requests:**

- Update ovos-plugin-manager requirement from \<2.0.0,\>=0.5.0 to \>=0.5.0,\<3.0.0 [\#34](https://github.com/OpenVoiceOS/padacioso/pull/34) ([dependabot[bot]](https://github.com/apps/dependabot))
- fix: padacioso speed [\#33](https://github.com/OpenVoiceOS/padacioso/pull/33) ([mikejgray](https://github.com/mikejgray))

## [1.0.1a1](https://github.com/OpenVoiceOS/padacioso/tree/1.0.1a1) (2025-06-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.0...1.0.1a1)

**Merged pull requests:**

- Update ovos-plugin-manager requirement from \<1.0.0,\>=0.5.0 to \>=0.5.0,\<2.0.0 [\#31](https://github.com/OpenVoiceOS/padacioso/pull/31) ([dependabot[bot]](https://github.com/apps/dependabot))



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
