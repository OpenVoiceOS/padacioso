# Changelog

## [2.4.2a1](https://github.com/OpenVoiceOS/padacioso/tree/2.4.2a1) (2026-09-26)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.4.1a1...2.4.2a1)

**Merged pull requests:**

- fix: spend max\_expansions as one pool, not a ration per line [\#113](https://github.com/OpenVoiceOS/padacioso/pull/113) ([openvoiceos-bot](https://github.com/openvoiceos-bot))

## [2.4.1a1](https://github.com/OpenVoiceOS/padacioso/tree/2.4.1a1) (2026-09-24)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.4.0a1...2.4.1a1)

**Merged pull requests:**

- fix: detach\_skill removes intents by skill\_id prefix, not substring [\#102](https://github.com/OpenVoiceOS/padacioso/pull/102) ([JarbasAl](https://github.com/JarbasAl))

## [2.4.0a1](https://github.com/OpenVoiceOS/padacioso/tree/2.4.0a1) (2026-09-18)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.6a2...2.4.0a1)

**Merged pull requests:**

- feat: bind a typed placeholder where the typed-slot map allows \(OVOS-INTENT-1 5.6\) [\#109](https://github.com/OpenVoiceOS/padacioso/pull/109) ([openvoiceos-bot](https://github.com/openvoiceos-bot))

## [2.3.6a2](https://github.com/OpenVoiceOS/padacioso/tree/2.3.6a2) (2026-09-18)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.6a1...2.3.6a2)

**Merged pull requests:**

- test: import FakeBus from ovos\_utils.fakebus [\#108](https://github.com/OpenVoiceOS/padacioso/pull/108) ([openvoiceos-bot](https://github.com/openvoiceos-bot))

## [2.3.6a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.6a1) (2026-09-18)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.5a2...2.3.6a1)

**Merged pull requests:**

- fix: pass required skill\_id kwarg to ovoscope e2e helpers [\#106](https://github.com/OpenVoiceOS/padacioso/pull/106) ([openvoiceos-bot](https://github.com/openvoiceos-bot))

## [2.3.5a2](https://github.com/OpenVoiceOS/padacioso/tree/2.3.5a2) (2026-09-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.5a1...2.3.5a2)

**Merged pull requests:**

- docs: fix unreachable case-insensitive confidence claim [\#90](https://github.com/OpenVoiceOS/padacioso/pull/90) ([JarbasAl](https://github.com/JarbasAl))

## [2.3.5a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.5a1) (2026-09-10)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.4a1...2.3.5a1)

**Merged pull requests:**

- fix: reject a section 8 payload that omits skill\_id [\#103](https://github.com/OpenVoiceOS/padacioso/pull/103) ([openvoiceos-bot](https://github.com/openvoiceos-bot))

## [2.3.4a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.4a1) (2026-09-07)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.3a1...2.3.4a1)

**Merged pull requests:**

- fix: break score ties by pattern specificity, not intent name [\#95](https://github.com/OpenVoiceOS/padacioso/pull/95) ([JarbasAl](https://github.com/JarbasAl))

## [2.3.3a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.3a1) (2026-09-07)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.2a1...2.3.3a1)

**Merged pull requests:**

- fix: key per-slot blacklists by language [\#93](https://github.com/OpenVoiceOS/padacioso/pull/93) ([JarbasAl](https://github.com/JarbasAl))

## [2.3.2a1](https://github.com/OpenVoiceOS/padacioso/tree/2.3.2a1) (2026-09-06)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/2.3.1a1...2.3.2a1)

**Merged pull requests:**

- fix: raise max\_expansions default, make it configurable, fix entity hard-truncation [\#91](https://github.com/OpenVoiceOS/padacioso/pull/91) ([JarbasAl](https://github.com/JarbasAl))

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

## [1.0.0](https://github.com/OpenVoiceOS/padacioso/tree/1.0.0) (2024-10-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/1.0.0a1...1.0.0)

**Merged pull requests:**

- Release 1.0.0a1 [\#30](https://github.com/OpenVoiceOS/padacioso/pull/30) ([github-actions[bot]](https://github.com/apps/github-actions))

## [1.0.0a1](https://github.com/OpenVoiceOS/padacioso/tree/1.0.0a1) (2024-10-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.2.4...1.0.0a1)

**Breaking changes:**

- feat!:pipeline factory [\#29](https://github.com/OpenVoiceOS/padacioso/pull/29) ([JarbasAl](https://github.com/JarbasAl))

## [0.2.4](https://github.com/OpenVoiceOS/padacioso/tree/0.2.4) (2024-10-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.2.4a1...0.2.4)

**Merged pull requests:**

- Release 0.2.4a1 [\#28](https://github.com/OpenVoiceOS/padacioso/pull/28) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.2.4a1](https://github.com/OpenVoiceOS/padacioso/tree/0.2.4a1) (2024-10-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.2.3a1...0.2.4a1)

**Merged pull requests:**

- fix:standardize\_lang [\#27](https://github.com/OpenVoiceOS/padacioso/pull/27) ([JarbasAl](https://github.com/JarbasAl))

## [0.2.3a1](https://github.com/OpenVoiceOS/padacioso/tree/0.2.3a1) (2024-10-14)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.2.2...0.2.3a1)

**Merged pull requests:**

- move unittests to padacioso repo [\#25](https://github.com/OpenVoiceOS/padacioso/pull/25) ([JarbasAl](https://github.com/JarbasAl))

## [0.2.2](https://github.com/OpenVoiceOS/padacioso/tree/0.2.2) (2024-10-14)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.2.2a2...0.2.2)

**Merged pull requests:**

- Release 0.2.2a2 [\#24](https://github.com/OpenVoiceOS/padacioso/pull/24) ([github-actions[bot]](https://github.com/apps/github-actions))

## [0.2.2a2](https://github.com/OpenVoiceOS/padacioso/tree/0.2.2a2) (2024-10-14)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.2a1...0.2.2a2)

**Merged pull requests:**

- feat:semver [\#23](https://github.com/OpenVoiceOS/padacioso/pull/23) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.2a1](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.2a1) (2024-07-20)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1...V0.2.2a1)

**Implemented enhancements:**

- feat/opm\_pipeline\_plugin [\#22](https://github.com/OpenVoiceOS/padacioso/pull/22) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.1](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1) (2023-12-29)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a9...V0.2.1)

**Merged pull requests:**

- 0.2.1 [\#21](https://github.com/OpenVoiceOS/padacioso/pull/21) ([github-actions[bot]](https://github.com/apps/github-actions))

## [V0.2.1a9](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a9) (2023-07-13)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a8...V0.2.1a9)

**Fixed bugs:**

- fix/fuzzy\_match scores [\#19](https://github.com/OpenVoiceOS/padacioso/pull/19) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.1a8](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a8) (2023-07-12)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a7...V0.2.1a8)

**Implemented enhancements:**

- feat/disambiguation [\#18](https://github.com/OpenVoiceOS/padacioso/pull/18) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.1a7](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a7) (2023-07-12)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a6...V0.2.1a7)

**Implemented enhancements:**

- feat/context + excluded keywords [\#17](https://github.com/OpenVoiceOS/padacioso/pull/17) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.1a6](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a6) (2023-06-02)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a5...V0.2.1a6)

**Fixed bugs:**

- remove spam LOG [\#14](https://github.com/OpenVoiceOS/padacioso/pull/14) ([JarbasAl](https://github.com/JarbasAl))

## [V0.2.1a5](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a5) (2023-05-16)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a4...V0.2.1a5)

**Implemented enhancements:**

- Adds support for Padatious `:0` syntax with unit tests [\#12](https://github.com/OpenVoiceOS/padacioso/pull/12) ([NeonDaniel](https://github.com/NeonDaniel))

## [V0.2.1a4](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a4) (2023-05-12)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a3...V0.2.1a4)

## [V0.2.1a3](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a3) (2023-05-11)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a2...V0.2.1a3)

## [V0.2.1a2](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a2) (2023-05-11)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.1a1...V0.2.1a2)

**Merged pull requests:**

- Optimize intent matching [\#10](https://github.com/OpenVoiceOS/padacioso/pull/10) ([NeonDaniel](https://github.com/NeonDaniel))

## [V0.2.1a1](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.1a1) (2023-05-06)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.2.0...V0.2.1a1)

**Merged pull requests:**

- add package data [\#9](https://github.com/OpenVoiceOS/padacioso/pull/9) ([emphasize](https://github.com/emphasize))

## [V0.2.0](https://github.com/OpenVoiceOS/padacioso/tree/V0.2.0) (2023-05-05)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.1.3a2...V0.2.0)

**Merged pull requests:**

- 0.2.0 [\#8](https://github.com/OpenVoiceOS/padacioso/pull/8) ([github-actions[bot]](https://github.com/apps/github-actions))

## [V0.1.3a2](https://github.com/OpenVoiceOS/padacioso/tree/V0.1.3a2) (2023-05-05)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/V0.1.3a1...V0.1.3a2)

**Merged pull requests:**

- Optimization and Confidence Adjustments [\#7](https://github.com/OpenVoiceOS/padacioso/pull/7) ([NeonDaniel](https://github.com/NeonDaniel))

## [V0.1.3a1](https://github.com/OpenVoiceOS/padacioso/tree/V0.1.3a1) (2023-05-03)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.1.1...V0.1.3a1)

**Fixed bugs:**

- Lowercase entity names in intent matches for backwards-compat. [\#5](https://github.com/OpenVoiceOS/padacioso/pull/5) ([NeonDaniel](https://github.com/NeonDaniel))
- Normalize braces around entities for compat with existing intents [\#4](https://github.com/OpenVoiceOS/padacioso/pull/4) ([NeonDaniel](https://github.com/NeonDaniel))

**Merged pull requests:**

- Automate releases and Update tests [\#6](https://github.com/OpenVoiceOS/padacioso/pull/6) ([NeonDaniel](https://github.com/NeonDaniel))

## [0.1.1](https://github.com/OpenVoiceOS/padacioso/tree/0.1.1) (2021-04-28)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/0.1.0...0.1.1)

## [0.1.0](https://github.com/OpenVoiceOS/padacioso/tree/0.1.0) (2021-04-28)

[Full Changelog](https://github.com/OpenVoiceOS/padacioso/compare/c962ff103520b15d1e75ec1e41fd95b236323b45...0.1.0)



\* *This Changelog was automatically generated by [github_changelog_generator](https://github.com/github-changelog-generator/github-changelog-generator)*
