from __future__ import unicode_literals
import frappe
from toolz.curried import merge

from gg_custom.api.booking_order import get_freight_rates


def validate(doc, self):
    if doc.gg_booking_order:
        existing = frappe.db.exists(
            "Sales Invoice", {"docstatus": 1, "gg_booking_order": doc.gg_booking_order}
        )
        if existing:
            frappe.throw(
                frappe._(
                    "{} already existing for {}. ".format(
                        frappe.get_desk_link("Sales Invoice", existing),
                        frappe.get_desk_link("Booking Order", doc.gg_booking_order),
                    )
                    + "If you want to proceed, please cancel the previous Invoice."
                )
            )


def on_submit(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc)


def on_cancel(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc, is_cancel=True)


def _update_booking_order(si, is_cancel=False):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "gg_booking_order": si.gg_booking_order},
        fields=["name", "total", "outstanding_amount"],
    )
    bo = frappe.get_cached_doc("Booking Order", si.gg_booking_order)
    if bo.docstatus == 2:
        return
    if sum([x.get("total") for x in invoices]) < bo.total_amount:
        bo.payment_status = "Unbilled"
    elif sum([x.get("outstanding_amount") for x in invoices]) == 0:
        bo.payment_status = "Paid"
    else:
        bo.payment_status = "Unpaid"

    if is_cancel:
        return

    freight_items = {v.get("item_code"): k for k, v in get_freight_rates().items()}
    bo.freight = []
    freight = frappe.get_all(
        "Sales Invoice Item",
        filters={
            "parent": ("in", [x.get("name") for x in invoices]),
            "item_code": ("in", [x for x in freight_items]),
        },
        fields=[
            "item_code",
            "qty",
            "rate",
            "amount",
            "description as item_description",
        ],
        order_by="parent, idx",
    )
    for row in freight:
        bo.append(
            "freight", merge(row, {"based_on": freight_items.get(row.get("item_code"))})
        )

    bo.charges = []
    charges = frappe.get_all(
        "Sales Invoice Item",
        filters={
            "parent": ("in", [x.get("name") for x in invoices]),
            "item_code": ("not in", freight_items),
        },
        fields=["item_code as charge_type", "amount as charge_amount"],
        order_by="parent, idx",
    )
    for row in charges:
        bo.append("charges", row)

    bo.set_totals()
    bo.flags.ignore_validate_update_after_submit = True
    bo.save()
