# Padacioso Accuracy & Speed — Implementation Status

## Items

- [x] 1. Entity value lookup: list → set (`add_entity`)
- [x] 2. Clamp confidence to [0.0, 1.0] (`_match`)
- [x] 3. Proportional wildcard penalty (`add_intent`, `_match`)
- [x] 4. Fix excluded-keywords substring bug (`_filter`)
- [x] 5. Fix greedy entity capture for multi-entity patterns (`add_intent`, `_match`)
- [x] 6. Skip cased pass for all-lowercase queries (`_match`)
- [x] 7. Early exit in `calc_intent` at high confidence
- [x] 8. Deterministic tie-breaking (`calc_intent`)
- [x] 9. Increase LRU cache size in `opm.py`
- [ ] 10. New tests (word-boundary exclusion, confidence clamp, tie-breaking, proportional penalty, multi-entity no-separator)
