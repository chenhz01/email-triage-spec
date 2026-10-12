# Alignment Audit (Rules 85-100 / 16 items) — email-triage-spec v0.1.1

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | Safety/Ethics section | N/A | Not a security-research repo; no dual-use surface. Fails closed (exit 2) on unreadable/invalid rule files; zero mail-server contact by design |
| 2 | Privacy/dezero | PASS | Only contact-style string is the permitted hcac4735@agent.qq.com (sample forward action + example email); no secrets/tokens/real names; grep `(sk-\|ghp_\|api[_-]?key\s*=\s*['"][A-Za-z0-9])` → 0 hits |
| 3 | Copyright boundary | PASS | Anchor comparisons (ericporres/email-triage-plugin, mypaios, stonefullstm/ai-email-triage) are structural restatements of public one-line descriptions (LLM plugin vs deterministic spec, platform vs single file, fuzzy vs auditable), no >50-char copied text; MIT LICENSE present, "zhengming contributors" |
| 4 | Fact-check annotation | PASS | Quickstart ~2 s marked [Measured] with repro `python self_test.py`; 200-rule classify <2 s and 100k-char body <2 s [Measured in c05/c06]; behavioral claims qualitative |
| 5 | Confidence grading | PASS | Policy implementation [High ≥80%]; token matching sufficiency [Medium]; long-term lint cleanliness [Low]; visible in Confidence section |
| 6 | PLAN B built-in | PASS | "Minimal Fallback (PLAN B)": two-step manual audit (priority-descending containment check + same-priority token sharing) with spreadsheet guidance |
| 7 | Timeout preset | PASS | Quickstart states "~2 s" total with per-step ≈0.5 s / ≈1 s markers |
| 8 | Rule-conflict arbitration | PASS | "Design Trade-offs" opens with priority order: auditability of the winner policy > lint precision without false alarms > expressiveness of conditions > coverage of mail-client actions |
| 9 | Version changelog | PASS | CHANGELOG.md v0.1.0 + v0.1.1; v0.1.1 lists the language-implication shadow fix, conflict-semantics clarification, and test delta 47→51 |
| 10 | Exemption instruction | N/A | Session-level rule; static repo content not applicable |
| 11 | External-knowledge cutoff | PASS | No vendor-specific time-sensitive claims; anchor facts restated from the 2026-10 candidate pool snapshot |
| 12 | Assumption explicitness | PASS | "[Core Assumptions]" section with 4 items (reproducibility, two-factor winner policy, token-substring vocabulary, linter surfaces unknown decisions) |
| 13 | Logic-check trio | PASS | self_test.py tiers: [A] functional (21 incl. a19b layering regression), [B] exception/CLI paths (15), [C] extreme edges (15: empty rules/missing fields/unicode subject+rules/100k-char body/200-rule timing/priority boundaries 0-100/-1/101/CRLF/extra fields). Final run: `python self_test.py` → `SUMMARY: PASS 51/51` |
| 14 | Socratic question | PASS | FAQ "When NOT to use this tool?" with 4 concrete anti-use-cases (LLM fuzzy triage, full mail OS, equality/regex/header needs, server-side execution) |
| 15 | Pareto improvement | PASS | v0.1.1: test count 47→51 (+8.5%) plus 2 correctness fixes (language-implication shadow detection, conflict restricted to same-priority ties); documented in CHANGELOG, suite re-run green |
| 16 | Ultimate fallback (≤60-word opener) | PASS | First paragraph = 58 words, contains what/who-needs-it judgment sentence |

Second-order effects (rule 16 bonus): PASS — "Limits & Second-order Effects" lists priority-soup config drift, pair-wise-only shadow detection, and substring false positives.

Scan evidence: `grep -rEn "(sk-\|ghp_\|api[_-]?key\s*=\s*['\"][A-Za-z0-9])" .` → 0 hits; `python self_test.py` → `SUMMARY: PASS 51/51`; `grep -rn "hcac4735@agent.qq.com" README.md examples/` → only permitted contact lines.
