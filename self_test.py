#!/usr/bin/env python3
"""Self-test for email-triage-spec. Run: python self_test.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import email_triage as et

TESTS = []


def t(fn):
    TESTS.append(fn)
    return fn


TD = None
SAMPLE = os.path.join(HERE, "examples", "rules.sample.json")
SAMPLE_EMAIL = os.path.join(HERE, "examples", "email.sample.json")

BASE = {"rules": [
    {"id": "r1", "priority": 50, "match": {"from_contains": ["@a.com"]},
     "action": "label:a"},
    {"id": "r2", "priority": 70, "match": {"subject_contains": ["urgent"]},
     "action": "label:urgent"},
], "default": {"priority": 0, "action": "inbox"}}

EMAIL = {"from": "x@b.com", "to": "me@here.com", "subject": "hello",
         "body": "plain"}


def setup():
    global TD
    TD = tempfile.mkdtemp(prefix="ets_test_")


def wp(name):
    return os.path.join(TD, name)


def wj(name, obj):
    p = wp(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    code = None
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = et.main(argv)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 0
    return code, out.getvalue(), err.getvalue()


def raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc:
        return
    raise AssertionError("expected %s" % exc.__name__)


# ---------------- [A] functional

@t
def a01_no_match_default():
    r = et.classify(EMAIL, *et.validate_spec(json.loads(json.dumps(BASE))))
    assert r["priority"] == 0 and r["action"] == "inbox" and r["matched"] == []


@t
def a02_from_match():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({**EMAIL, "from": "who@a.com"}, *spec)
    assert r["action"] == "label:a" and r["matched"] == ["r1"]


@t
def a03_subject_match():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({**EMAIL, "subject": "URGENT: fix"}, *spec)
    assert r["action"] == "label:urgent"


@t
def a04_body_keyword_match():
    rules = [{"id": "kw", "priority": 30,
              "match": {"body_keywords": ["invoice"]}, "action": "label:fin"}]
    r = et.classify({**EMAIL, "body": "see attached invoice #7"}, rules,
                    BASE["default"])
    assert r["action"] == "label:fin"


@t
def a05_to_match():
    rules = [{"id": "to", "priority": 20,
              "match": {"to_contains": ["team@here.com"]}, "action": "label:t"}]
    r = et.classify({**EMAIL, "to": "team@here.com"}, rules, BASE["default"])
    assert r["action"] == "label:t"


@t
def a06_highest_priority_wins():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({"from": "who@a.com", "subject": "urgent now"}, *spec)
    assert r["action"] == "label:urgent" and r["matched"] == ["r1", "r2"]


@t
def a07_tie_keeps_file_order():
    rules = [
        {"id": "first", "priority": 50, "match": {"subject_contains": ["x"]},
         "action": "label:first"},
        {"id": "second", "priority": 50, "match": {"subject_contains": ["x"]},
         "action": "label:second"},
    ]
    r = et.classify({"subject": "xox"}, rules, BASE["default"])
    assert r["action"] == "label:first"


@t
def a08_case_insensitive():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({"from": "WHO@A.COM"}, *spec)
    assert r["action"] == "label:a"


@t
def a09_multiple_matched_listed():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({"from": "who@a.com", "subject": "urgent"}, *spec)
    assert set(r["matched"]) == {"r1", "r2"}


@t
def a10_forward_action():
    rules = [{"id": "f", "priority": 90,
              "match": {"from_contains": ["@alerts.io"]},
              "action": "forward:hcac4735@agent.qq.com"}]
    r = et.classify({"from": "n@alerts.io"}, rules, BASE["default"])
    assert r["action"] == "forward:hcac4735@agent.qq.com"


@t
def a11_classify_cli_text():
    code, out, _ = run_cli(["classify", "--rules", SAMPLE,
                            "--email", SAMPLE_EMAIL])
    assert code == 0 and "action=archive" in out and "newsletters" in out


@t
def a12_classify_cli_json():
    code, out, _ = run_cli(["classify", "--rules", SAMPLE,
                            "--email", SAMPLE_EMAIL, "--json"])
    data = json.loads(out)
    assert code == 0 and data["action"] == "archive"


@t
def a13_lint_clean_sample():
    rules, _ = et.load_spec(SAMPLE)
    assert et.lint_rules(rules) == []


@t
def a14_duplicate_id_rejected():
    bad = {"rules": [
        {"id": "d", "priority": 1, "match": {"subject_contains": ["x"]},
         "action": "archive"},
        {"id": "d", "priority": 2, "match": {"subject_contains": ["y"]},
         "action": "archive"}]}
    raises(ValueError, et.validate_spec, bad)


@t
def a15_priority_range_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["priority"] = 101
    raises(ValueError, et.validate_spec, bad)


@t
def a16_bad_action_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["action"] = "Label With Spaces"
    raises(ValueError, et.validate_spec, bad)


@t
def a17_empty_match_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["match"] = {}
    raises(ValueError, et.validate_spec, bad)


@t
def a18_shadowed_detected():
    rules = [
        {"id": "broad", "priority": 90, "match": {"from_contains": ["@a.com"]},
         "action": "label:work"},
        {"id": "narrow", "priority": 20, "match": {"from_contains": ["boss@a.com"]},
         "action": "label:boss"},
    ]
    issues = et.lint_rules(rules)
    assert any(x["type"] == "shadowed" and x["rule"] == "narrow" for x in issues)


@t
def a19_conflict_detected():
    rules = [
        {"id": "low", "priority": 50, "match": {"subject_contains": ["report"]},
         "action": "archive"},
        {"id": "high", "priority": 50, "match": {"subject_contains": ["report"]},
         "action": "label:now"},
    ]
    issues = et.lint_rules(rules)
    assert any(x["type"] == "conflict" and x["rule"] == "high" for x in issues)


@t
def a19b_layering_not_conflict():
    rules = [
        {"id": "low", "priority": 10, "match": {"subject_contains": ["report"]},
         "action": "archive"},
        {"id": "high", "priority": 95, "match": {"subject_contains": ["report"]},
         "action": "label:now"},
    ]
    assert et.lint_rules(rules) == []


@t
def a20_unknown_match_key_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["match"] = {"cc_contains": ["x"]}
    raises(ValueError, et.validate_spec, bad)

# ---------------- [B] exception / CLI paths

@t
def b01_missing_rules_exit2():
    code, _, err = run_cli(["lint", "--rules", wp("nope.json")])
    assert code == 2 and "error" in err


@t
def b02_malformed_rules_json():
    p = wp("m.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write("{bad")
    code, _, _ = run_cli(["lint", "--rules", p])
    assert code == 2


@t
def b03_rules_not_object():
    raises(ValueError, et.validate_spec, [1, 2])


@t
def b04_rules_list_missing():
    raises(ValueError, et.validate_spec, {"default": {}})


@t
def b05_rule_not_object():
    raises(ValueError, et.validate_spec, {"rules": ["x"]})


@t
def b06_rule_missing_id():
    raises(ValueError, et.validate_spec,
           {"rules": [{"priority": 1, "match": {"subject_contains": ["x"]},
                       "action": "archive"}]})


@t
def b07_rule_missing_match():
    raises(ValueError, et.validate_spec,
           {"rules": [{"id": "x", "priority": 1, "action": "archive"}]})


@t
def b08_match_not_object():
    raises(ValueError, et.validate_spec,
           {"rules": [{"id": "x", "priority": 1, "match": ["a"],
                       "action": "archive"}]})


@t
def b09_tokens_not_strings():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["match"]["from_contains"] = [1, 2]
    raises(ValueError, et.validate_spec, bad)


@t
def b10_empty_token_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["match"]["from_contains"] = ["  "]
    raises(ValueError, et.validate_spec, bad)


@t
def b11_priority_bool_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["priority"] = True
    raises(ValueError, et.validate_spec, bad)


@t
def b12_email_missing_exit2():
    code, _, _ = run_cli(["classify", "--rules", SAMPLE,
                          "--email", wp("nope.json")])
    assert code == 2


@t
def b13_email_not_object_exit2():
    p = wj("e.json", [1])
    code, _, _ = run_cli(["classify", "--rules", SAMPLE, "--email", p])
    assert code == 2


@t
def b14_lint_exit1_on_issues():
    p = wj("bad.json", {"rules": [
        {"id": "a", "priority": 90, "match": {"subject_contains": ["x"]},
         "action": "label:a"},
        {"id": "b", "priority": 10, "match": {"subject_contains": ["x"]},
         "action": "archive"}]})
    code, out, _ = run_cli(["lint", "--rules", p])
    assert code == 1 and "shadowed" in out


@t
def b15_lint_exit0_clean():
    code, out, _ = run_cli(["lint", "--rules", SAMPLE])
    assert code == 0 and "no issues" in out

# ---------------- [C] extreme edges

@t
def c01_empty_rules_default():
    r = et.classify(EMAIL, [], BASE["default"])
    assert r["action"] == "inbox" and r["priority"] == 0


@t
def c02_missing_email_fields_tolerated():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({}, *spec)
    assert r["action"] == "inbox"
    r2 = et.classify({"from": "who@a.com"}, *spec)
    assert r2["action"] == "label:a"


@t
def c03_unicode_subject():
    rules = [{"id": "cn", "priority": 60,
              "match": {"subject_contains": ["紧急"]}, "action": "label:cn"}]
    r = et.classify({"subject": "服务器紧急告警"}, rules, BASE["default"])
    assert r["action"] == "label:cn"


@t
def c04_unicode_in_rules_ok():
    spec = et.validate_spec({"rules": [{"id": "u", "priority": 5,
                                        "match": {"body_keywords": ["发票"]},
                                        "action": "label:fin"}]})
    assert spec[0][0]["id"] == "u"


@t
def c05_huge_body_timing():
    rules = [{"id": "big", "priority": 1,
              "match": {"body_keywords": ["needle"]}, "action": "archive"}]
    email = {"body": "hay " * 25000 + "needle"}
    t0 = time.time()
    r = et.classify(email, rules, BASE["default"])
    assert time.time() - t0 < 2.0 and r["action"] == "archive"


@t
def c06_many_rules_timing():
    rules = [{"id": "r%03d" % i, "priority": i % 101,
              "match": {"subject_contains": ["tok%d" % i]},
              "action": "label:%d" % i} for i in range(200)]
    t0 = time.time()
    r = et.classify({"subject": "has tok199 inside"}, rules, BASE["default"])
    assert time.time() - t0 < 2.0 and r["action"] == "label:199"


@t
def c07_priority_boundaries_ok():
    spec = et.validate_spec({"rules": [
        {"id": "lo", "priority": 0, "match": {"subject_contains": ["a"]},
         "action": "archive"},
        {"id": "hi", "priority": 100, "match": {"subject_contains": ["b"]},
         "action": "label:b"}]})
    assert len(spec[0]) == 2


@t
def c08_priority_negative_rejected():
    bad = json.loads(json.dumps(BASE))
    bad["rules"][0]["priority"] = -1
    raises(ValueError, et.validate_spec, bad)


@t
def c09_empty_body_no_match():
    rules = [{"id": "kw", "priority": 30,
              "match": {"body_keywords": ["x"]}, "action": "archive"}]
    assert et.classify({"body": ""}, rules, BASE["default"])["matched"] == []


@t
def c10_extra_email_fields_ignored():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    r = et.classify({**EMAIL, "attachments": 99, "flag": True}, *spec)
    assert r["action"] == "inbox"


@t
def c11_crlf_body():
    rules = [{"id": "kw", "priority": 30,
              "match": {"body_keywords": ["total"]}, "action": "archive"}]
    r = et.classify({"body": "line1\r\ntotal: 5\r\n"}, rules, BASE["default"])
    assert r["action"] == "archive"


@t
def c12_lint_report_serializable():
    rules = [
        {"id": "a", "priority": 90, "match": {"subject_contains": ["x"]},
         "action": "label:a"},
        {"id": "b", "priority": 10, "match": {"subject_contains": ["x"]},
         "action": "archive"}]
    json.loads(json.dumps(et.lint_rules(rules)))


@t
def c13_overlapping_same_action_no_issue():
    rules = [
        {"id": "a", "priority": 90, "match": {"subject_contains": ["x"]},
         "action": "label:keep"},
        {"id": "b", "priority": 10, "match": {"subject_contains": ["x"]},
         "action": "label:keep"}]
    assert et.lint_rules(rules) == []


@t
def c14_disjoint_rules_no_issue():
    rules, _ = et.load_spec(SAMPLE)
    assert et.lint_rules(rules) == []


@t
def c15_classify_result_serializable():
    spec = et.validate_spec(json.loads(json.dumps(BASE)))
    json.loads(json.dumps(et.classify(EMAIL, *spec)))


def main():
    setup()
    ok = 0
    fails = []
    for fn in TESTS:
        try:
            fn()
            ok += 1
        except Exception as e:  # noqa: BLE001
            fails.append((fn.__name__, repr(e)))
    for name, e in fails:
        print("FAIL %s: %s" % (name, e))
    total = len(TESTS)
    print("SUMMARY: %s %d/%d" % ("PASS" if not fails else "FAIL", ok, total))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
