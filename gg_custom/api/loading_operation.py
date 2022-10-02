import frappe
from frappe.query_builder import Criterion
from toolz.curried import merge


@frappe.whitelist()
def query(doctype, txt, searchfield, start, page_len, filters):
    LoadingOperation = frappe.qb.DocType("Loading Operation")
    LoadingOperationBookingOrder = frappe.qb.DocType("Loading Operation Booking Order")

    fields = [
        LoadingOperation.name,
        LoadingOperation.shipping_order,
        LoadingOperation.vehicle,
    ]
    q = (
        frappe.qb.from_(LoadingOperation)
        .left_join(LoadingOperationBookingOrder)
        .on(LoadingOperationBookingOrder.parent == LoadingOperation.name)
        .where(
            (LoadingOperation.docstatus == 1)
            & (LoadingOperationBookingOrder.parentfield == "on_loads")
        )
        .where(Criterion.any([x.like(f"%{txt}%") for x in fields]))
        .where(
            LoadingOperationBookingOrder.booking_order == filters.get("booking_order")
        )
        .select(*fields)
        .distinct()
        .orderby(LoadingOperation.posting_datetime)
        .limit(page_len)
        .offset(start)
    )

    return q.run()
