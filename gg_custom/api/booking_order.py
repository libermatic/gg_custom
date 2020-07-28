from __future__ import unicode_literals
import frappe
import json
from frappe.contacts.doctype.address.address import get_company_address
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from toolz.curried import compose, merge, concatv, unique, map, filter


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
    get_changes = compose(
        merge,
        map(lambda x: {x[0]: x[2]}),
        filter(lambda x: x[0] in ["status", "current_station"]),
        lambda x: x.get("changed", []),
        json.loads,
        lambda x: x.get("data"),
    )

    def get_version_message(version):
        changes = version.get("changes")
        status = changes.get("status")
        current_station = changes.get("current_station")
        if status in ["Draft", "Loaded", "Unloaded"]:
            return ""
        if not status and not current_station:
            return "In Transit"
        if not status and current_station:
            return "At {}".format(current_station)
        if status and not current_station:
            return status
        return "{} at {}".format(changes.get("status"), changes.get("current_station"))

    get_versions = compose(
        filter(lambda x: x.get("message")),
        map(
            lambda x: {
                "datetime": x.get("creation"),
                "status": x.get("changes").get("status", "In Transit"),
                "message": get_version_message(x),
            }
        ),
        filter(lambda x: x.get("changes")),
        map(lambda x: merge(x, {"changes": get_changes(x)})),
        lambda x: frappe.get_all(
            "Version",
            filters={"ref_doctype": "Booking Order", "docname": x},
            fields=["creation", "data"],
        ),
    )

    def get_loading_message(loading):
        operation = (
            "Loaded"
            if loading.get("parentfield") == "on_loads"
            else "Unloaded"
            if loading.get("parentfield") == "off_loads"
            else "Operation"
        )
        return {
            "datetime": loading.get("posting_datetime"),
            "status": operation,
            "message": "{} at {}".format(operation, loading.get("station")),
            "link": "#Form/Loading Operation/{}".format(loading.get("name")),
        }

    get_loadings = compose(
        map(get_loading_message),
        lambda x: frappe.db.sql(
            """
                SELECT
                    lo.name,
                    lo.station,
                    lo.posting_datetime,
                    lobo.parentfield
                FROM `tabLoading Operation` AS lo
                LEFT JOIN `tabLoading Operation Booking Order` AS lobo ON
                    lobo.parent = lo.name
                WHERE
                    lo.docstatus = 1 AND
                    lobo.booking_order = %(booking_order)s
            """,
            values={"booking_order": x},
            as_dict=1,
        ),
    )

    return sorted(
        concatv(get_versions(name), get_loadings(name)),
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
