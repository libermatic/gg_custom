from __future__ import unicode_literals
import frappe
from toolz.curried import (
    merge,
    compose,
    concatv,
    valmap,
    first,
    groupby,
    excepts,
    map,
    filter,
)

from gg_custom.api.booking_order import get_freight_rates


def validate(doc, self):
    def get_error_type():
        if doc.gg_loading_operation:
            existing = frappe.db.exists(
                "Sales Invoice",
                {
                    "name": ("!=", doc.name),
                    "docstatus": 1,
                    "gg_booking_order": doc.gg_booking_order,
                    "gg_loading_operation": doc.gg_loading_operation,
                },
            )
            if existing:
                return "freight"
        else:
            existing = frappe.db.sql(
                """
                    SELECT COUNT(name) FROM `tabSales Invoice` WHERE
                        name != %(name)s AND
                        docstatus = 1 AND
                        gg_booking_order = %(booking_order)s AND
                        IFNULL(gg_loading_operation, '') = ''
                """,
                values={"name": doc.name, "booking_order": doc.gg_booking_order},
            )[0][0]
            if existing:
                return "charges"
        return None

    if doc.gg_booking_order:
        error_type = get_error_type()
        if error_type:
            frappe.throw(
                frappe._(
                    "Sales Invoice for {} already existing for {}. ".format(
                        error_type,
                        frappe.get_desk_link("Booking Order", doc.gg_booking_order),
                    )
                    + "If you want to proceed, please cancel the previous Invoice."
                )
            )

        if doc.gg_loading_operation:
            _validate_freight_qty(doc)


def on_submit(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(doc, is_charge=not doc.gg_loading_operation)


def on_cancel(doc, self):
    if doc.gg_booking_order:
        _update_booking_order(
            doc, is_charge=not doc.gg_loading_operation, is_cancel=True
        )


def _update_booking_order(si, is_charge=False, is_cancel=False):
    bo = frappe.get_cached_doc("Booking Order", si.gg_booking_order)
    if bo.docstatus == 2:
        return

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "gg_booking_order": si.gg_booking_order},
        fields=["name", "total", "outstanding_amount"],
    )
    if sum([x.get("total") for x in invoices]) < bo.total_amount:
        bo.payment_status = "Unbilled"
    elif sum([x.get("outstanding_amount") for x in invoices]) == 0:
        bo.payment_status = "Paid"
    else:
        bo.payment_status = "Unpaid"

    if is_cancel:
        return

    if is_charge:
        _update_charges(bo)
    else:
        _update_freight(bo, si.gg_loading_operation)

    bo.set_totals()
    bo.flags.ignore_validate_update_after_submit = True
    bo.save()


def _update_freight(bo, loading_operation):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "gg_booking_order": bo.name,
            "gg_loading_operation": loading_operation,
        },
    )

    get_items = compose(valmap(first), groupby("gg_bo_detail"), frappe.get_all)
    items = get_items(
        "Sales Invoice Item",
        filters={"parent": ("in", [x.get("name") for x in invoices])},
        fields=["item_code", "rate", "description as item_description", "gg_bo_detail"],
        order_by="parent, idx",
    )
    for row in bo.freight:
        rate = items.get(row.name, {}).get("rate")
        if row.rate != rate:
            row.rate = rate
            row.amount = rate * _get_freight_qty(row)


def _update_charges(bo):
    invoices = frappe.get_all(
        "Sales Invoice",
        filters=[
            ["docstatus", "=", 1],
            ["gg_booking_order", "=", bo.name],
            ["ifnull(gg_loading_operation, '')", "=", ""],
        ],
    )
    bo.charges = []
    charges = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": ("in", [x.get("name") for x in invoices]),},
        fields=["item_code as charge_type", "amount as charge_amount"],
        order_by="parent, idx",
    )
    for row in charges:
        bo.append("charges", row)


def _validate_freight_qty(doc):
    bo = frappe.get_cached_doc("Booking Order", doc.gg_booking_order)
    get_freight_row = compose(
        excepts(StopIteration, first, lambda _: None),
        lambda x: filter(lambda row: row.name == x, bo.freight),
    )

    for item in doc.items:
        if item.gg_bo_detail:
            freight_row = get_freight_row(item.gg_bo_detail)
            if not freight_row:
                frappe.throw(
                    frappe._(
                        "Invalid Booking Order Freight Detail found in row #{} for {}".format(
                            item.idx, frappe.get_desk_link("Sales Invoice", doc.name)
                        )
                    )
                )

            total_qty = (
                frappe.get_all(
                    "Sales Invoice Item",
                    filters={"docstatus": 1, "gg_bo_detail": item.gg_bo_detail},
                    fields=["sum(qty)"],
                    as_list=1,
                )[0][0]
                or 0
            )
            if total_qty + item.qty > _get_freight_qty(freight_row):
                frappe.throw(
                    frappe._(
                        "Total Qty in #{} for {} will exceed Freight Qty declared in {}".format(
                            item.idx,
                            frappe.get_desk_link("Sales Invoice", doc.name),
                            frappe.get_desk_link("Booking Order", doc.gg_booking_order),
                        )
                    )
                )


def _get_freight_qty(freight_row):
    if freight_row.based_on == "Packages":
        return freight_row.no_of_packages
    if freight_row.based_on == "Weight":
        return freight_row.weight_actual
    return 0
