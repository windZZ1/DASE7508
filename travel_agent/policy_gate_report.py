"""Evaluation report for the booking policy gate (member 5).

Runs a labeled suite of valid and invalid booking requests through a real
``PolicyGate`` + ``BookingService`` (SQLite) and reports:

  * blocked violations   (TP) - invalid requests the gate rejected
  * incorrect rejections (FP) - valid requests the gate wrongly rejected
  * missed violations    (FN) - invalid requests the gate wrongly approved
  * correct approvals    (TN) - valid requests the gate approved

Each decision is also checked against the database: a rejection must leave the
order store empty, and an approval must produce exactly one order with the
expected total.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .agent import Task
from .booking import BookingService
from .hotel_search import HotelSearchService
from .policy_gate import PolicyGate


@dataclass(frozen=True)
class Case:
    name: str
    task: Task
    hotel_id: object
    coupon_code: object
    expected_approved: bool
    expected_error: str = ""
    expected_total_cents: int = 0


def _base(**overrides):
    params = dict(
        city="Dubai",
        check_in="2026-12-01",
        check_out="2026-12-02",
        max_total_cents=15000,
        min_rating="4.5",
        currency="USD",
    )
    params.update(overrides)
    return params


def build_cases():
    return [
        # ---- valid requests (must approve) ----
        Case("cheapest qualifying w/ coupon", Task(**_base()),
             "dubai-a", "SAVE20", True, "", 14000),
        Case("qualifying without coupon", Task(**_base()),
             "dubai-b", None, True, "", 14500),
        Case("budget exactly at limit", Task(**_base(max_total_cents=14000)),
             "dubai-a", "SAVE20", True, "", 14000),
        Case("rating exactly at bound", Task(**_base(min_rating="4.6")),
             "dubai-a", "SAVE20", True, "", 14000),
        # ---- invalid requests (must reject) ----
        Case("over budget (no coupon)", Task(**_base()),
             "dubai-a", None, False, "budget_exceeded"),
        Case("one cent over budget", Task(**_base(max_total_cents=13999)),
             "dubai-a", "SAVE20", False, "budget_exceeded"),
        Case("rating below minimum", Task(**_base()),
             "dubai-c", None, False, "rating_below_minimum"),
        Case("rating just below bound", Task(**_base(min_rating="4.7")),
             "dubai-a", "SAVE20", False, "rating_below_minimum"),
        Case("coupon not applicable", Task(**_base()),
             "dubai-b", "SAVE20", False, "unknown_hotel_or_coupon"),
        Case("unknown hotel", Task(**_base()),
             "dubai-x", None, False, "unknown_hotel_or_coupon"),
        Case("bad arguments", Task(**_base()),
             123, None, False, "invalid_booking_arguments"),
        Case("mixed violation", Task(**_base(max_total_cents=10000, min_rating="4.7")),
             "dubai-a", None, False, "rating_below_minimum"),
    ]


def run_report(gate=None):
    """Run every labeled case and return per-case rows plus aggregate counts."""
    cases = build_cases()
    owns_temp = gate is None
    temp = None
    if owns_temp:
        temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        trusted = HotelSearchService()
        booking = BookingService(
            Path(temp.name) / "orders.sqlite3",
            search_service=trusted,
            trial_id="policy-report",
        )
        gate = PolicyGate(booking, trusted_search_service=trusted)

    rows = []
    tp = fp = fn = tn = 0
    reason_mismatches = 0
    db_mismatches = 0
    for case in cases:
        gate.reset("policy-report")
        result = gate.book_hotel(case.task, case.hotel_id, case.coupon_code)
        orders = gate.list_orders()
        approved = bool(result.get("ok"))

        if case.expected_approved:
            if approved and len(orders) == 1 and (
                orders[0]["total_cents"] == case.expected_total_cents
            ):
                tn += 1
                label = "TN (correct approval)"
            elif approved:
                tn += 1
                label = "TN (approval; db anomaly)"
                db_mismatches += 1
            else:
                fp += 1
                label = "FP (incorrect rejection)"
        else:
            if approved:
                fn += 1
                label = "FN (missed violation)"
                db_mismatches += 1
            elif not orders and result.get("error") == case.expected_error:
                tp += 1
                label = "TP (blocked violation)"
            else:
                tp += 1
                label = "TP (blocked; reason/db check)"
                if result.get("error") != case.expected_error:
                    reason_mismatches += 1
                if orders:
                    db_mismatches += 1

        rows.append((case, result, orders, label))

    if owns_temp:
        temp.cleanup()
    return {
        "rows": rows,
        "valid_total": sum(1 for c in cases if c.expected_approved),
        "invalid_total": sum(1 for c in cases if not c.expected_approved),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "reason_mismatches": reason_mismatches,
        "db_mismatches": db_mismatches,
    }


def print_report(report):
    print("Booking policy gate evaluation (member 5)")
    print("=" * 92)
    print(f"{'case':<28} {'expected':<9} {'actual':<9} {'orders':<7} outcome")
    print("-" * 92)
    for case, result, orders, label in report["rows"]:
        exp = "approve" if case.expected_approved else "reject"
        act = "approve" if result.get("ok") else "reject"
        line = f"{case.name:<28} {exp:<9} {act:<9} {len(orders):<7} {label}"
        if result.get("error"):
            line += "  [" + result["error"] + "]"
        print(line)
    print("-" * 92)
    print(f"valid requests (should approve)  : {report['valid_total']}")
    print(f"  correctly approved (TN)        : {report['tn']}")
    print(f"  incorrectly rejected (FP)      : {report['fp']}")
    print(f"invalid requests (should reject) : {report['invalid_total']}")
    print(f"  blocked violations (TP)        : {report['tp']}")
    print(f"  missed violations (FN)         : {report['fn']}")
    print(f"reason mismatches                : {report['reason_mismatches']}")
    print(f"database mismatches              : {report['db_mismatches']}")
    print("-" * 92)
    v = report["valid_total"]
    iv = report["invalid_total"]
    fp_rate = (report["fp"] / v * 100) if v else 0.0
    block_rate = (report["tp"] / iv * 100) if iv else 0.0
    print(f"false-positive rate (incorrect rejections): {fp_rate:.1f}%")
    print(f"violation-block rate (TP among violations): {block_rate:.1f}%")


def main():
    print_report(run_report())


if __name__ == "__main__":
    main()

