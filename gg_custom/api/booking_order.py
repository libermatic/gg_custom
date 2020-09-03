from __future__ import unicode_literals
import frappe
import json
from frappe.contacts.doctype.address.address import (
    get_company_address,
    get_address_display,
)
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.stock.get_item_details import get_item_price
from toolz.curried import (
    compose,
    merge,
    unique,
    sliding_window,
    concat,
    groupby,
    valmap,
    first,
    dissoc,
    map,
    filter,
)


@frappe.whitelist()
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
            x.get("booking_order")
            for x in get_orders_for(station=filters.get("station"))
        ]
        if booking_orders:
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
            x.get("booking_order")
            for x in get_orders_for(shipping_order=filters.get("shipping_order"))
        ]
        if booking_orders:
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
            "loading_unit",
            "no_of_packages",
            "weight_actual",
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
            if log.get("loading_unit") == "Weight":
                return "{} {} units by weight at {}".format(
                    log.get("activity"),
                    abs(log.get("weight_actual")),
                    log.get("station"),
                )
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
            return "#Form/Loading Operation/{}".format(log.get("loading_operation"))

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

    def postprocess(source, target):
        items = [dissoc(x.as_dict(), "idx") for x in target.items]
        target.items = []
        freight_rates = get_freight_rates()
        for row in source.freight:
            freight_item = freight_rates.get(row.get("based_on")) or {}
            target.append(
                "items",
                {
                    "item_code": freight_item.get("item_code"),
                    "price_list_rate": freight_item.get("rate"),
                    "qty": row.get("qty"),
                    "rate": row.get("rate"),
                    "stock_uom": freight_item.get("uom"),
                    "uom": freight_item.get("uom"),
                    "description": row.get("item_description"),
                },
            )

        for row in items:
            target.append("items", merge(row, {"qty": 1}))

        set_invoice_missing_values(source, target)

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
        postprocess,
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
    def get_qty(row):
        if row.get("loading_unit") == "Packages":
            return row.get("no_of_packages")
        if row.get("loading_unit") == "Weight":
            return row.get("weight_actual")
        return 0

    def set_qty(row):
        qty = get_qty(row)
        return merge(row, {"qty": qty, "available": qty})

    get_result = compose(list, map(set_qty), frappe.db.sql)

    if station:
        return get_result(
            """
                SELECT
                    bl.booking_order,
                    MAX(bl.loading_unit) AS loading_unit,
                    SUM(bl.no_of_packages) AS no_of_packages,
                    SUM(bl.weight_actual) AS weight_actual,
                    bl.bo_detail,
                    bofd.item_description AS description
                FROM `tabBooking Log` AS bl
                LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                    bofd.name = bl.bo_detail
                WHERE bl.station = %(station)s
                GROUP BY bl.bo_detail HAVING
                    SUM(bl.no_of_packages) > 0 OR SUM(bl.weight_actual) > 0
            """,
            values={"station": station},
            as_dict=1,
        )

    if shipping_order:
        return get_result(
            """
                SELECT
                    bl.booking_order,
                    MAX(bl.loading_unit) AS loading_unit,
                    -SUM(bl.no_of_packages) AS no_of_packages,
                    -SUM(bl.weight_actual) AS weight_actual,
                    bl.bo_detail,
                    bofd.item_description AS description
                FROM `tabBooking Log` AS bl
                LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                    bofd.name = bl.bo_detail
                WHERE bl.shipping_order = %(shipping_order)s
                GROUP BY bl.bo_detail HAVING
                    SUM(bl.no_of_packages) < 0 OR SUM(bl.weight_actual) < 0
            """,
            values={"shipping_order": shipping_order},
            as_dict=1,
        )

    return []


@frappe.whitelist()
def get_order_details(bo_detail, station=None, shipping_order=None):
    if station:
        return frappe.db.sql(
            """
                SELECT
                    SUM(bl.no_of_packages) AS no_of_packages,
                    SUM(bl.weight_actual) AS weight_actual,
                    bofd.item_description AS description
                FROM `tabBooking Log` AS bl
                LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                    bofd.name = bl.bo_detail
                WHERE
                    bl.station = %(station)s AND
                    bl.bo_detail = %(bo_detail)s
            """,
            values={"station": station, "bo_detail": bo_detail,},
            as_dict=1,
        )[0]

    if shipping_order:
        return frappe.db.sql(
            """
                SELECT
                    -SUM(no_of_packages) AS no_of_packages,
                    -SUM(weight_actual) AS weight_actual,
                    bofd.item_description AS description
                FROM `tabBooking Log` AS bl
                LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                    bofd.name = bl.bo_detail
                WHERE
                    bl.shipping_order = %(shipping_order)s AND
                    bl.bo_detail = %(bo_detail)s
            """,
            values={"shipping_order": shipping_order, "bo_detail": bo_detail,},
            as_dict=1,
        )[0]

    return {}


@frappe.whitelist()
def update_party_details(name):
    doc = frappe.get_cached_value(
        "Booking Order", name, ["consignor", "consignee"], as_dict=1
    )

    for field in ["consignor", "consignee"]:
        party_name, address_name = frappe.get_cached_value(
            "Booking Party", doc.get(field), ["booking_party_name", "primary_address"]
        )
        address_display = get_address_display(address_name)
        frappe.db.set_value(
            "Booking Order",
            name,
            {
                "{}_name".format(field): party_name,
                "{}_address".format(field): address_name,
                "{}_address_display".format(field): address_display,
            },
        )


def get_freight_rates():
    price_list = frappe.get_cached_value(
        "Selling Settings", None, "selling_price_list",
    )

    def get_rate(item):
        args = {"price_list": price_list, "uom": item.get("uom")}
        rate = get_item_price(args, item.get("item_code"), ignore_party=True)
        if rate:
            return rate[0][1]

        return 0

    get_freight_items = compose(
        valmap(first),
        groupby("based_on"),
        map(lambda x: merge(x, {"rate": get_rate(x)})),
        frappe.db.sql,
    )

    return get_freight_items(
        """
            SELECT name AS item_code, stock_uom AS uom, gg_freight_based_on AS based_on
            FROM `tabItem`
            WHERE gg_freight_based_on IN ('Packages', 'Weight')
        """,
        as_dict=1,
    )


def get_loading_conversion_factor(qty, unit, no_of_packages, weight_actual):
    if unit == "Packages" and no_of_packages:
        return frappe.utils.flt(qty) / no_of_packages
    if unit == "Weight" and weight_actual:
        return frappe.utils.flt(qty) / weight_actual

    return None


@frappe.whitelist()
def get_description_options(booking_order):
    return [
        x[0]
        for x in frappe.get_all(
            "Booking Order Freight Detail",
            filters={"parent": booking_order},
            fields=["item_description"],
            as_list=1,
        )
    ]

