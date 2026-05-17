import frappe


def on_submit(doc, method):
    _update_booking_orders(
        [x for x in doc.references if x.reference_doctype == "Sales Invoice"]
    )


def on_cancel(doc, method):
    _update_booking_orders(
        [x for x in doc.references if x.reference_doctype == "Sales Invoice"]
    )


def _update_booking_orders(references):
    bos = [
        frappe.get_doc("Booking Order", x)
        for x in set(
            frappe.get_cached_value(
                "Sales Invoice", si.reference_name, "gg_booking_order"
            )
            for si in references
        )
        if x
    ]

    for bo in bos:
        invoices = frappe.get_all(
            "Sales Invoice",
            filters={"docstatus": 1, "gg_booking_order": bo.name},
            fields=["total", "outstanding_amount"],
        )
        if sum(x.get("total") for x in invoices) < bo.total_amount:
            bo.payment_status = "Unbilled"
        elif sum(x.get("outstanding_amount") for x in invoices) == 0:
            bo.payment_status = "Paid"
        else:
            bo.payment_status = "Unpaid"
        bo.save()
