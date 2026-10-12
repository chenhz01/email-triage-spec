# Changelog — email-triage-spec

## v0.1.1 — 2026-10-12

- Fixed: shadowed-rule detection now uses language implication (every token of
  the lower rule contains a token of the higher rule, same match keys) instead
  of raw token equality/containment overlap, which over-flagged intentional
  layering (e.g. a VIP rule layered above its domain rule).
- Clarified conflict semantics: only *same-priority* overlaps with different
  actions are flagged; different-priority overlaps are deterministic layering.
- Fixed: lint pass no longer skips the `action ==- equality` early-out before
  overlap checks (pair-level short-circuit added, lint on 200 rules <2 s).
- Self-review round: test suite grew 47 → 51 cases (added layering-is-not-
  conflict regression, unicode rules, CRLF bodies, 200-rule timing, extra
  email fields).

## v0.1.0 — 2026-10-11

- Initial cut (session-interrupted build): declarative rule schema
  (id/priority/match/action + default), strict validation (unique ids, 0-100
  priority, known match keys, action grammar), deterministic classifier
  (highest priority wins, file-order ties, full matched-id list), linter for
  shadowed + same-priority conflict rules, CLI classify/lint, sample rules and
  email examples, 47 self-test cases.
