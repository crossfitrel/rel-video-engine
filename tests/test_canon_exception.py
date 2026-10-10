# -*- coding: utf-8 -*-
"""אוכף ללקח L59 — חריגת קאנון מוצהרת.

שער קאנון שצודק במקרה שאין לו דרך לדעת עליו צריך נתון, לא עקיפה. החריגה
מורידה HARD_FAIL ל-WARNING, לעולם לא ל-PASS, ורק לשערים ברשימת היתר צרה.
הבדיקות האלה הן האוכף: מי שיהפוך את זה ל-PASS או ירחיב את הרשימה — יפיל אחת.
"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(HERE, "tools")
sys.path.insert(0, TOOLS)

import canon_lint  # noqa: E402

VALID = {
    "reason": "חלון הפתיחה מצלם אנשים שאינם המרואיין באזור החלפה — אינו ניתן לפרסום",
    "approved_by": "הראל",
    "at": "2026-09-21",
    "evidence": "INPUT_eyes/contact_01-02 · 00:00.0-00:09.0",
}


def _wd(exc=None):
    d = tempfile.mkdtemp(prefix="canon_exc_")
    man = {"name": "בדיקה", "project_id": "prj_test"}
    if exc is not None:
        man["canon_exceptions"] = exc
    with open(os.path.join(d, "project_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False)
    return d


def test_allowlist_is_narrow():
    """רשימת ההיתר חייבת להישאר צרה. הרחבה היא החלטה, לא תופעת לוואי."""
    assert canon_lint.CANON_EXCEPTABLE == frozenset({"hook_protected"}), (
        "רשימת ההיתר השתנתה. הרחבה של CANON_EXCEPTABLE היא החלטת קאנון "
        "שדורשת אישור מפורש של הראל ועדכון הלקח L59.")


def test_no_manifest_no_exceptions():
    good, rejected = canon_lint._canon_exceptions(_wd())
    assert good == {} and rejected == []


def test_valid_exception_is_accepted():
    good, rejected = canon_lint._canon_exceptions(_wd({"hook_protected": VALID}))
    assert "hook_protected" in good and rejected == []


def test_rule_outside_allowlist_is_rejected_loudly():
    good, rejected = canon_lint._canon_exceptions(
        _wd({"broll_throwdown_scope": VALID}))
    assert good == {} and rejected and "broll_throwdown_scope" in rejected[0]


def test_missing_approver_is_rejected():
    bad = dict(VALID); bad.pop("approved_by")
    good, rejected = canon_lint._canon_exceptions(_wd({"hook_protected": bad}))
    assert good == {} and "approved_by" in rejected[0]


def test_missing_date_is_rejected():
    bad = dict(VALID); bad["at"] = "   "
    good, rejected = canon_lint._canon_exceptions(_wd({"hook_protected": bad}))
    assert good == {} and rejected


def test_short_reason_is_rejected():
    """נימוק שאי אפשר לבדוק אינו נימוק."""
    bad = dict(VALID); bad["reason"] = "כי כן"
    good, rejected = canon_lint._canon_exceptions(_wd({"hook_protected": bad}))
    assert good == {} and rejected and "נימוק" in rejected[0]


def test_bad_manifest_does_not_crash():
    d = tempfile.mkdtemp(prefix="canon_exc_bad_")
    open(os.path.join(d, "project_manifest.json"), "w").write("{לא json")
    good, rejected = canon_lint._canon_exceptions(d)
    assert good == {} and rejected


def test_exception_never_becomes_pass():
    """הבדיקה החשובה ביותר: חריגה מורידה ל-WARNING ולא מעלימה את הממצא."""
    src = open(os.path.join(TOOLS, "canon_lint.py"), encoding="utf-8").read()
    assert '_hook_level = "WARNING" if _hook_exc else "HARD_FAIL"' in src, (
        "מסלול החריגה שונה. חריגה מוצהרת חייבת להוריד ל-WARNING — "
        "אסור שתהפוך את hook_protected ל-PASS.")
    assert '"PASS" if _hook_exc' not in src


def test_reason_reaches_the_report():
    """נימוק שלא מגיע לדוח הוא נימוק שאיש לא יקרא."""
    src = open(os.path.join(TOOLS, "canon_lint.py"), encoding="utf-8").read()
    assert "_hook_note" in src and "חריגה מוצהרת" in src
