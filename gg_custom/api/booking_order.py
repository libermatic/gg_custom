from __future__ import unicode_literals
import frappe
import json
from frappe.contacts.doctype.address.address import get_company_address
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from toolz.curried import compose, merge, unique, sliding_window, concat, map, filter


def query(doctype, txt, searchfield, start, page_len, filters):
    _type = filters.get("type")
    fields = [
        "name",
        "source_station",
        "consignor",
        "consignor_name",
        "destination_station",
        "consignee",
        "consignee_name",
    ]

    values = {
        "txt": "%%%s%%" % txt,
        "start": start,
        "page_len": page_len,
    }

    conds = [
        "docstatus = 1",
        "({})".format(" OR ".join(["{} LIKE %(txt)s".format(x) for x in fields])),
        "name IN %(booking_orders)s",
    ]
    if _type == "on_load":
        booking_orders = [
            x.booking_order for x in get_orders_for(station=filters.get("station"))
        ]
        return frappe.db.sql(
            """
                SELECT {fields} FROM `tabBooking Order`
                WHERE {conds} LIMIT %(start)s, %(page_len)s
            """.format(
                fields=", ".join(fields), conds=" AND ".join(conds)
            ),
            values=merge(values, {"booking_orders": booking_orders}),
        )
    if _type == "off_load":
        booking_orders = [
            x.booking_order
            for x in get_orders_for(shipping_order=filters.get("shipping_order"))
        ]
        return frappe.db.sql(
            """
                SELECT {fields} FROM `tabBooking Order`
                WHERE {conds} LIMIT %(start)s, %(page_len)s
            """.format(
                fields=", ".join(fields), conds=" AND ".join(conds)
            ),
            values=merge(values, {"booking_orders": booking_orders}),
        )
    return []


@frappe.whitelist()
def get_history(name):
    booking_logs = frappe.get_all(
        "Booking Log",
        filters={"booking_order": name},
        fields=[
            "'Booking Log' as doctype",
            "posting_datetime",
            "booking_order",
            "shipping_order",
            "station",
            "activity",
            "loading_operation",
            "no_of_packages",
        ],
        order_by="posting_datetime",
    )

    get_shipping_logs = compose(
        concat,
        map(
            lambda x: frappe.get_all(
                "Shipping Log",
                filters={
                    "shipping_order": x[0].get("shipping_order"),
                    "activity": ("in", ["Stopped", "Moving"]),
                    "posting_datetime": (
                        "between",
                        [x[0].get("posting_datetime"), x[1].get("posting_datetime")],
                    ),
                },
                fields=[
                    "'Shipping Log' as doctype",
                    "posting_datetime",
                    "shipping_order",
                    "station",
                    "activity",
                ],
                order_by="posting_datetime",
            )
            if x[0].get("shipping_order")
            else []
        ),
        sliding_window(2),
    )

    shipping_logs = get_shipping_logs(
        booking_logs + [{"posting_datetime": frappe.utils.now()}]
    )

    def get_message(log):
        if log.get("doctype") == "Booking Log":
            return "{} {} packages at {}".format(
                log.get("activity"), abs(log.get("no_of_packages")), log.get("station")
            )

        if log.get("doctype") == "Shipping Log":
            prepo = "to" if log.get("activity") == "Moving" else "at"
            return "{} {} {}".format(log.get("activity"), prepo, log.get("station"))

        return ""

    def get_link(log):
        if log.get("doctype") == "Shipping Log":
            return "#Form/Shipping Order/{}".format(log.get("shipping_order"))

        if log.get("doctype") == "Booking Log" and log.get("loading_operation"):
            "#Form/Loading Operation/{}".format(log.get("loading_operation"))

        return ""

    def get_event(log):
        return {
            "datetime": log.get("posting_datetime"),
            "status": log.get("activity"),
            "message": get_message(log),
            "link": get_link(log),
        }

    return sorted(
        [get_event(x) for x in concat([booking_logs, shipping_logs])],
        key=lambda x: frappe.utils.get_datetime(x.get("datetime")),
    )


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):
    bill_to = frappe.flags.args and frappe.flags.args.get("bill_to")
    taxes_and_charges = frappe.flags.args and frappe.flags.args.get("taxes_and_charges")

    def set_invoice_missing_values(source, target):
        target.customer = _get_or_create_customer(source_name, bill_to)
        target.update(
            frappe.model.utils.get_fetch_values(
                "Sales Invoice", "customer", target.customer
            )
        )
        target.customer_address = frappe.get_cached_value(
            "Booking Order", source_name, "{}_address".format(bill_to)
        )
        if target.customer_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Sales Invoice", "customer_address", target.customer_address
                )
            )
        target.taxes_and_charges = taxes_and_charges
        target.ignore_pricing_rule = 1
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        target.update(get_company_address(target.company))
        if target.company_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Sales Invoice", "company_address", target.company_address
                )
            )

    return frappe.model.mapper.get_mapped_doc(
        "Booking Order",
        source_name,
        {
            "Booking Order": {
                "doctype": "Sales Invoice",
                "fieldmap": {"name": "px_booking_order"},
                "validation": {"docstatus": ["=", 1]},
            },
            "Booking Order Charge": {
                "doctype": "Sales Invoice Item",
                "field_map": {"charge_type": "item_code", "charge_amount": "rate"},
            },
        },
        target_doc,
        set_invoice_missing_values,
    )


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    invoices = [
        frappe.get_cached_doc("Sales Invoice", x.get("name"))
        for x in frappe.get_all(
            "Sales Invoice",
            filters={
                "docstatus": 1,
                "gg_booking_order": source_name,
                "outstanding_amount": [">", 0],
            },
            order_by="posting_date, name",
        )
    ]

    if not invoices:
        frappe.throw(frappe._("No outstanding invoices to create payment"))

    if len(list(unique([x.customer for x in invoices]))) != 1:
        frappe.throw(
            frappe._(
                "Multiple invoices found for separate parties. "
                "Please create Payment Entry manually from Sales Invoice."
            )
        )

    pe = get_payment_entry("Sales Invoice", invoices[0].name)
    if len(invoices) > 1:
        outstanding_amount = sum([x.outstanding_amount for x in invoices])
        pe.paid_amount = outstanding_amount
        pe.received_amount = outstanding_amount
        pe.references = []
        for si in invoices:
            pe.append(
                "references",
                {
                    "reference_doctype": si.doctype,
                    "reference_name": si.name,
                    "bill_no": si.get("bill_no"),
                    "due_date": si.get("due_date"),
                    "total_amount": si.grand_total,
                    "outstanding_amount": si.outstanding_amount,
                    "allocated_amount": si.outstanding_amount,
                },
            )
    return pe


def _get_or_create_customer(booking_order_name, bill_to):
    msg = frappe._("Cannot create Invoice without Customer")
    if not bill_to:
        frappe.throw(msg)

    booking_party_name = frappe.db.get_value(
        "Booking Order", booking_order_name, bill_to
    )
    if not booking_party_name:
        frappe.throw(msg)

    booking_party = frappe.get_cached_doc("Booking Party", booking_party_name)
    if not booking_party:
        frappe.throw(msg)

    if booking_party.customer:
        return booking_party.customer

    booking_party.create_customer()
    return booking_party.customer


def get_orders_for(station=None, shipping_order=None):
    if station:
        return frappe.db.sql(
            """
                SELECT
                    booking_order,
                    SUM(no_of_packages) AS no_of_packages,
                    SUM(weight_actual) AS weight_actual,
                    SUM(goods_value) AS goods_value
                FROM `tabBooking Log`
                WHERE
                    station = %(station)s AND
                    activity IN ('Booked', 'Loaded', 'Unloaded')
                GROUP BY booking_order HAVING SUM(no_of_packages) > 0
            """,
            values={"station": station},
            as_dict=1,
        )

    if shipping_order:
        return frappe.db.sql(
            """
                SELECT
                    booking_order,
                    -SUM(no_of_packages) AS no_of_packages,
                    -SUM(weight_actual) AS weight_actual,
                    -SUM(goods_value) AS goods_value
                FROM `tabBooking Log`
                WHERE
                    shipping_order = %(shipping_order)s AND
                    activity IN ('Booked', 'Loaded', 'Unloaded')
                GROUP BY booking_order HAVING SUM(no_of_packages) < 0
            """,
            values={"shipping_order": shipping_order,},
            as_dict=1,
        )

    return []
