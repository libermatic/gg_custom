# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe

from erpnext.accounts.report.accounts_receivable_summary.accounts_receivable_summary import (
    execute as accounts_receivable_summary,
)


def execute(filters=None):
    result = accounts_receivable_summary(filters)
    columns = _get_columns(result)
    data = _get_data(result)
    return columns, data


def _get_columns(report):
    columns = report[0]
    fields = [
        "party",
        "party_name",
        "invoiced",
        "paid",
        "outstanding",
        "range1",
        "range2",
        "range3",
        "range4",
        "range5",
        "total_due",
    ]
    return [x for x in columns if x.get("fieldname") in fields] + [
        {
            "label": "Booking Party",
            "fieldname": "booking_party",
            "fieldtype": "Link",
            "options": "Booking Party",
            "width": 180,
        }
    ]


def _get_data(report):
    rows = sorted(report[1] or [], key=lambda x: x.get("party_name"))
    booking_party_by_customer_ids = (
        {
            x.get("customer"): x.get("name")
            for x in frappe.get_all(
                "Booking Party",
                fields=["name", "customer"],
                filters={"customer": ("in", [x.get("party") for x in rows])},
                order_by="modified asc"
            )
        }
        if rows
        else {}
    )

    return [
        {
            **x,
            "paid": x.get("advance") + x.get("paid"),
            "booking_party": booking_party_by_customer_ids.get(x.get("party")),
        }
        for x in rows
    ]
