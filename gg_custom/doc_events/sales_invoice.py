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
        _update_booking_order(doc)


def _update_booking_order(si):
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

    bo.charges = []
    charges = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ("in", [x.get("name") for x in invoices])},
        fields=["item_code as charge_type", "sum(amount) as charge_amount"],
        group_by="item_code",
        order_by="parent, idx",
    )
    for charge in charges:
        bo.append("charges", charge)

    bo.total_amount = sum([x.get("charge_amount") for x in charges])
    bo.flags.ignore_validate_update_after_submit = True
    bo.save()
