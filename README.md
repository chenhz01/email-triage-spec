# email-triage-spec

email-triage-spec defines a declarative rule format — sender/recipient/subject/keyword token conditions mapped to a 0–100 priority and an action — plus a deterministic classifier and a linter that flags malformed rules, dead (shadowed) rules, and same-priority conflicts. Use it when your inbox rules have grown past a screenful and nobody can say anymore which rule wins, or why.

## Problem

Mail rules accrete. A rule set written over years has overlapping conditions, two rules fighting at the same priority with different actions, and narrow rules buried under broad ones that make them dead code. Every mail client hides this as execution-order semantics that nobody can audit. What is missing is a *specification layer*: rules as reviewable JSON, a documented winner policy, and a checker that says "this rule can never fire" or "these two rules tie arbitrarily" before you ship the config.

## How it works

1. **Rule format** — a rules file is `{"rules": [...], "default": {...}}`; each rule has a unique `id`, `priority` (int 0–100), `match` (any combination of `from_contains`, `to_contains`, `subject_contains`, `body_keywords` — lists of case-insensitive tokens), and an `action` (`name` or `name:target`, e.g. `archive`, `label:work`, `forward:hcac4735@agent.qq.com`).
2. **Classifier** — an email matches a rule if any token occurs (case-insensitive) in the corresponding field. The highest-priority matching rule wins; equal priorities keep file order; no match falls to `default`. The result records every matched rule id, not just the winner.
3. **Linter** — `lint` reports *shadowed* rules (a lower-priority rule whose matching language is fully covered by a higher-priority rule with a different action — it can never win) and *conflicts* (same-priority overlaps with different actions — the tie-break is arbitrary). Exit `1` when issues exist.

## Quickstart

Measured on a laptop, Python 3.10: total **~2 s**.

```bash
# ~0.5 s: classify the bundled sample email against the sample rules
python email_triage.py classify --rules examples/rules.sample.json \
    --email examples/email.sample.json

# ~0.5 s: audit a rule set for dead rules and tie conflicts
python email_triage.py lint --rules examples/rules.sample.json

# ~1 s: self-test (51 cases)
python self_test.py
```

## Why not X

- **[ericporres/email-triage-plugin](https://github.com/ericporres/email-triage-plugin)** — a plugin template that turns Claude into an email triage assistant with three-tier classification. It spends LLM tokens per email and its judgment is not reproducible; this spec is pure deterministic rules — same input, same verdict, zero inference cost.
- **[mypaios](https://github.com/mypaios/mypaios)** — a local-first personal AI OS whose email triage runs inside a full platform (chat, agents, video analysis). You adopt the whole OS to get triage; here the deliverable is one spec file and one checker you can wire into any client.
- **[stonefullstm/ai-email-triage](https://github.com/stonefullstm/ai-email-triage)** — combines heuristics, embeddings, and LLMs to classify and prioritize mail. Powerful for fuzzy semantic categories, but a black box for auditing; this repo targets the opposite end: rules a human can fully reason about, with conflicts surfaced mechanically.

## Minimal Fallback (PLAN B)

Cannot run the linter? Do the two-rule audit by hand — it catches most damage: (1) sort rules by priority descending and check every rule against each higher-priority rule: if the higher one's condition tokens contain yours (e.g. your `boss@a.com` under their `@corp.com`), your rule is dead on that overlap; (2) group rules by priority and check for same-priority pairs sharing any token with different actions — that tie is decided by file order and is almost always a bug. A spreadsheet is enough for rule sets under ~50 entries.

## Design Trade-offs

Priority order: **auditability of the winner policy > lint precision without false alarms > expressiveness of conditions > coverage of mail-client actions.** The winner policy is deliberately blunt (priority, then file order) so it can be reasoned about; the linter deliberately refuses to warn on *layered* overlaps (different priorities, different actions) because intentional layering is normal — warning there would train users to ignore it. Token matching is substring-based, so `@a.com` covers `boss@a.com` (useful) but also matches unintended substrings (documented).

## Limits & Second-order Effects

- Substring tokens cannot express "exactly this address", field equality, or header conditions; rule authors compensate with longer tokens.
- The shadowed check is per-rule-pair; a rule dead only under the *union* of several higher rules is not reported.
- Actions are strings the spec validates syntactically, not executes — wiring to real mail clients is yours.
- As rule sets grow, owners may add priority layers to silence lint warnings, turning the config into priority soup (second-order: the audit tool reshapes the config it audits).

## FAQ

**Can I use this against a real mailbox?** Not directly — it classifies one JSON email object at a time. Fetch/export glue is deliberately out of scope.

**Why substring matching instead of exact addresses?** Domains (`@corp.com`) and subject fragments are the common case; exactness can be approximated with the full address as a token.

**What happens on a tie?** File order wins, and `lint` tells you a tie exists so file order stops being an accident.

**When NOT to use this tool?** (1) You want an LLM to triage fuzzy, semantic categories — use a plugin like ericporres/email-triage-plugin. (2) You need a full local mail OS — mypaios. (3) Your rules need equality semantics, regex, or header conditions — the token format will fight you. (4) You want the tool to *execute* actions against a mail server — nothing here talks to mail infrastructure.

## [Core Assumptions]

1. Triage decisions should be reproducible and auditable; nondeterministic classification is out of scope by design.
2. Priority (0–100) plus file-order tie-break fully specifies the winner; no hidden execution-order semantics.
3. Any-of-token substring matching over four fields is expressive enough for the common triage vocabulary (domains, addresses, subject fragments, keywords).
4. The linter's job is to surface *decisions the author did not know they made* (dead rules, arbitrary ties), not to redesign intentional layering.

## Confidence

That the classifier and linter implement the documented policy: **High (≥80%)** — 51 self-test cases cover winners, ties, shadows, conflicts, and malformed configs. That token-substring matching suffices for real inbox vocabularies: **Medium**. That users will keep rules lint-clean over time: **Low** — see second-order effects.

*as of 2026-10-12*

---

Part of the [zhengming-toolbox](https://github.com/chenhz01/zhengming-toolbox) — 55 purpose-built AI-engineering tools across neglected niches.

Related tools: [focus-data-aggregator](https://github.com/chenhz01/focus-data-aggregator) · [git-history-hygiene](https://github.com/chenhz01/git-history-hygiene) · [todo-expiry-ledger](https://github.com/chenhz01/todo-expiry-ledger)
