import frappe


def validate(doc, method):
    validate_invoice(doc)


def validate_invoice(doc, throw=True):
    if doc.flags.skip_validation:
        return None

    if doc.gg_booking_order:
        existing = frappe.db.exists(
            "Sales Invoice",
            {
                "name": ("!=", doc.name),
                "docstatus": 1,
                "gg_booking_order": doc.gg_booking_order,
            },
        )
        if existing:
            msg = frappe._(
                f"Sales Invoice already exists for {frappe.get_desk_link('Booking Order', doc.gg_booking_order)}. "
                + "If you want to proceed, please cancel the previous Invoice."
            )
            if throw:
                frappe.throw(msg)

            return msg

    return None


def on_submit(doc, method):
    if doc.gg_booking_order:
        _update_booking_order(doc)


def on_cancel(doc, method):
    if doc.gg_booking_order:
        _update_booking_order(doc, is_cancel=True)


def _update_booking_order(si, is_cancel=False):
    bo = frappe.get_cached_doc("Booking Order", si.gg_booking_order)
    if bo.docstatus == 2:
        return

    invoices = frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "gg_booking_order": si.gg_booking_order},
        fields=["name", "total", "outstanding_amount"],
    )
    if sum(x.get("total") for x in invoices) < bo.total_amount:
        bo.payment_status = "Unbilled"
    elif sum(x.get("outstanding_amount") for x in invoices) == 0:
        bo.payment_status = "Paid"
    else:
        bo.payment_status = "Unpaid"

    if not is_cancel:
        _update_charges(bo)
        _update_freight(bo, si)
        bo.set_totals()
        bo.flags.ignore_validate_update_after_submit = True

    bo.save()


def _update_freight(bo, si):
    for sii in [x for x in si.items if x.gg_update_freight]:
        freight = next((x for x in bo.freight if x.name == sii.gg_bo_detail), None)
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
