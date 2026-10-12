#!/usr/bin/env python3
"""email-triage-spec: declarative triage rule format + rule conflict detector.

A rules file declares: matching conditions (sender/recipient/subject/keyword
tokens, case-insensitive) -> priority (0-100) + action. The engine classifies
an email to the highest-priority matching rule (file order breaks ties); the
linter flags malformed rules, shadowed rules, and conflicting overlaps.
Pure stdlib, all data local.
"""
import argparse
import json
import re
import sys

RULES_VERSION = 1
MATCH_KEYS = ("from_contains", "to_contains", "subject_contains",
              "body_keywords")
ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(:\S+)?$")


# ---------------------------------------------------------------- validation

def validate_spec(data):
    """Validate a spec dict in place; returns (rules, default). Raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError("rules file must be a JSON object")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError("rules file must contain a 'rules' list")
    default = data.get("default", {"priority": 0, "action": "inbox"})
    if not isinstance(default, dict) or "priority" not in default \
            or "action" not in default:
        raise ValueError("'default' must be an object with priority and action")
    seen_ids = set()
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError("rule %d: must be an object" % i)
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError("rule %d: missing non-empty 'id'" % i)
        if rid in seen_ids:
            raise ValueError("rule %d: duplicate id %r" % (i, rid))
        seen_ids.add(rid)
        pr = rule.get("priority")
        if not isinstance(pr, int) or isinstance(pr, bool) or not 0 <= pr <= 100:
            raise ValueError("rule %r: priority must be an int 0-100" % rid)
        match = rule.get("match")
        if not isinstance(match, dict) or not match:
            raise ValueError("rule %r: 'match' must be a non-empty object" % rid)
        for key, tokens in match.items():
            if key not in MATCH_KEYS:
                raise ValueError("rule %r: unknown match key %r (valid: %s)"
                                 % (rid, key, ", ".join(MATCH_KEYS)))
            if not isinstance(tokens, list) or not all(
                    isinstance(x, str) and x.strip() for x in tokens):
                raise ValueError("rule %r: match.%s must be a list of "
                                 "non-empty strings" % (rid, key))
        action = rule.get("action")
        if not isinstance(action, str) or not ACTION_RE.match(action):
            raise ValueError("rule %r: bad action %r (expected 'name' or "
                             "'name:target')" % (rid, action))
    return rules, default


def load_spec(path):
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError("invalid rules JSON: %s" % e)
    return validate_spec(data)


# ---------------------------------------------------------------- classify

def _tokens_match(tokens, text):
    t = (text or "").lower()
    return any(tok.lower() in t for tok in tokens)


def rule_matches(rule, email):
    m = rule["match"]
    checks = (
        ("from_contains", email.get("from", "")),
        ("to_contains", email.get("to", "")),
        ("subject_contains", email.get("subject", "")),
        ("body_keywords", email.get("body", "")),
    )
    return any(key in m and _tokens_match(m[key], text) for key, text in checks)


def classify(email, rules, default):
    """Return {priority, action, matched}; highest priority wins, ties keep
    file order. Empty condition lists never match."""
    matched = []
    winner = None
    for rule in rules:
        if not rule_matches(rule, email):
            continue
        matched.append(rule["id"])
        if winner is None or rule["priority"] > winner["priority"]:
            winner = rule
    if winner is None:
        return {"priority": default["priority"], "action": default["action"],
                "matched": []}
    return {"priority": winner["priority"], "action": winner["action"],
            "matched": matched}


# ---------------------------------------------------------------- lint

def _lists_overlap(ta, tb):
    """Exact, substring-containment overlap between two token lists
    (so '@a.com' overlaps 'boss@a.com')."""
    if not ta or not tb:
        return False
    if set(ta) & set(tb):
        return True
    return any(a in b or b in a for a in ta for b in tb)


def _overlap(a, b):
    """Approximate overlap: any token overlap in a shared match key."""
    for key in MATCH_KEYS:
        ta = [t.lower() for t in a["match"].get(key, [])]
        tb = [t.lower() for t in b["match"].get(key, [])]
        if _lists_overlap(ta, tb):
            return True
    return False


def _implied_by(b_tokens, a_tokens):
    """True if every b-token contains some a-token as a substring, i.e. any
    text matching a b-token also matches an a-token (language B ⊆ language A
    under any-of-token semantics)."""
    return all(any(a in b for a in a_tokens) for b in b_tokens)


def lint_rules(rules):
    """Return a list of {rule, type, detail} issues. Structural validity is
    assumed (validate_spec ran); this pass finds semantic conflicts:

    - shadowed: rule B's matching language is fully covered by a
      higher-priority rule A (same match keys, every B token contains an A
      token) with a different action — B can never win.
    - conflict: two same-priority rules share overlapping token conditions
      but declare different actions — the file-order tie-break is arbitrary.
    """
    issues = []
    for i, rule in enumerate(rules):
        for j in range(i):
            other = rules[j]
            if rule["action"] == other["action"]:
                continue
            if rule["priority"] < other["priority"] and \
                    set(rule["match"]) <= set(other["match"]) and \
                    all(_implied_by([t.lower() for t in rule["match"][k]],
                                    [t.lower() for t in other["match"][k]])
                        for k in rule["match"]):
                issues.append({
                    "rule": rule["id"], "type": "shadowed",
                    "detail": "matching language fully covered by "
                              "higher-priority rule %r (p%d vs p%d) with a "
                              "different action (%s vs %s); this rule can "
                              "never win"
                              % (other["id"], other["priority"],
                                 rule["priority"], other["action"],
                                 rule["action"])})
            elif rule["priority"] == other["priority"] and \
                    _overlap(other, rule):
                issues.append({
                    "rule": rule["id"], "type": "conflict",
                    "detail": "overlapping conditions with rule %r map to "
                              "different actions (%s vs %s) at the same "
                              "priority %d; file order decides arbitrarily"
                              % (other["id"], rule["action"], other["action"],
                                 rule["priority"])})
    return issues


# ---------------------------------------------------------------- CLI

def cmd_classify(args):
    rules, default = load_spec(args.rules)
    with open(args.email, "r", encoding="utf-8") as f:
        try:
            email = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError("invalid email JSON: %s" % e)
    if not isinstance(email, dict):
        raise ValueError("email file must be a JSON object")
    result = classify(email, rules, default)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("priority=%d action=%s matched=%s"
              % (result["priority"], result["action"],
                 ",".join(result["matched"]) or "-"))
    return 0


def cmd_lint(args):
    rules, _default = load_spec(args.rules)
    issues = lint_rules(rules)
    if not issues:
        print("lint: no issues found (%d rules)" % len(rules))
        return 0
    for issue in issues:
        print("[%s] %s: %s" % (issue["type"], issue["rule"], issue["detail"]))
    print("lint: %d issue(s)" % len(issues))
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="email-triage",
        description="Declarative email triage rules + conflict detector.")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="classify one email JSON")
    c.add_argument("--rules", required=True)
    c.add_argument("--email", required=True)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_classify)
    l = sub.add_parser("lint", help="detect rule conflicts and shadows")
    l.add_argument("--rules", required=True)
    l.set_defaults(fn=cmd_lint)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except (ValueError, OSError) as e:
        print("error: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
