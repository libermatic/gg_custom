from __future__ import unicode_literals
import frappe
from toolz.curried import compose, unique, map, filter


def on_submit(doc, method):
    _update_booking_orders(
        [x for x in doc.references if x.reference_doctype == "Sales Invoice"]
    )


def on_cancel(doc, method):
    _update_booking_orders(
        [x for x in doc.references if x.reference_doctype == "Sales Invoice"]
    )


def _update_booking_orders(references):
    get_booking_orders = compose(
        map(lambda x: frappe.get_doc("Booking Order", x)),
        filter(None),
        unique,
        map(
            lambda x: frappe.get_cached_value(
                "Sales Invoice", x.reference_name, "gg_booking_order"
            )
        ),
    )
    for bo in get_booking_orders(references):
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"docstatus": 1, "gg_booking_order": bo.name},
            fields=["total", "outstanding_amount"],
        )
        if sum([x.get("total") for x in invoices]) < bo.total_amount:
            bo.payment_status = "Unbilled"
        elif sum([x.get("outstanding_amount") for x in invoices]) == 0:
            bo.payment_status = "Paid"
        else:
            bo.payment_status = "Unpaid"
        bo.save()

