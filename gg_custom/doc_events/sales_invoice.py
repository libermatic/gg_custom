import frappe
from toolz.curried import (
    compose,
    first,
    excepts,
    map,
    filter,
)


def validate(doc, method):
    validate_invoice(doc)


def validate_invoice(doc, throw=True):
    if doc.flags.skip_validation:
        return None

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
            msg = frappe._(
                "Sales Invoice for {} already exists for {}. ".format(
                    error_type,
                    frappe.get_desk_link("Booking Order", doc.gg_booking_order),
                )
                + "If you want to proceed, please cancel the previous Invoice."
            )
            if throw:
                frappe.throw(msg)

            return msg

        if doc.flags.validate_loading and doc.gg_loading_operation:
            msg = _validate_freight_qty(doc)
            if msg:
                if throw:
                    frappe.throw(msg)

                return msg

    return None


def on_submit(doc, method):
    if doc.gg_booking_order:
        _update_booking_order(doc, is_charge=not doc.gg_loading_operation)


def on_cancel(doc, method):
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

    if not is_cancel:
        if is_charge:
            _update_charges(bo)
        else:
            _update_freight(bo, si)
        bo.set_totals()
        bo.flags.ignore_validate_update_after_submit = True

    bo.save()


def _update_freight(bo, si):
    get_freight_row = compose(
        excepts(StopIteration, first, lambda _: None),
        lambda name: filter(lambda x: x.name == name, bo.freight),
    )
    for sii in [x for x in si.items if x.gg_update_freight]:
        freight = get_freight_row(sii.gg_bo_detail)
        if freight:
            freight.based_on = frappe.get_cached_value(
                "Item", sii.item_code, "gg_freight_based_on"
            )
            if freight.based_on == "Packages":
                freight.no_of_packages = sii.qty
            elif freight.based_on == "Weight":
                freight.weight_actual = sii.qty
            freight.rate = sii.rate
            freight.amount = sii.amount


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
        filters={"parent": ("in", [x.get("name") for x in invoices])},
        fields=[
            "item_code as charge_type",
            "amount as charge_amount",
            "description as item_description",
        ],
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
                return frappe._(
                    "Invalid Booking Order Freight Detail found in row #{} for {}".format(
                        item.idx, frappe.get_desk_link("Sales Invoice", doc.name)
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
            if frappe.utils.flt(total_qty + item.qty, precision=3) > _get_freight_qty(
                freight_row
            ):
                return frappe._(
                    "Total Qty will exceed Freight Qty declared in {}".format(
                        frappe.get_desk_link("Booking Order", doc.gg_booking_order),
                    )
                )

    return None


def _get_freight_qty(freight_row):
    if freight_row.based_on == "Packages":
        return frappe.utils.flt(freight_row.no_of_packages, precision=3)
    if freight_row.based_on == "Weight":
        return frappe.utils.flt(freight_row.weight_actual, precision=3)
    return 0.0
