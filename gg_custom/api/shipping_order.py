from __future__ import unicode_literals
import frappe
from toolz.curried import compose, merge, concat, valmap, keymap, keyfilter, map, filter
from frappe.contacts.doctype.address.address import get_company_address

from gg_custom.api.booking_order import get_freight_rates


@frappe.whitelist()
def query(doctype, txt, searchfield, start, page_len, filters):
    station = filters.get("station")
    cond = (
        " OR ".join(
            [
                "so.initial_station = %(station)s",
                "so.final_station = %(station)s",
                "sots.station = %(station)s",
            ]
        )
        if station
        else "1 = 1"
    )
    return frappe.db.sql(
        """
            SELECT DISTINCT so.name, so.vehicle, so.driver_name, so.driver
            FROM `tabShipping Order` AS so
            LEFT JOIN `tabShipping Order Transit Station` AS sots
                ON sots.parent = so.name
			WHERE ({cond}) AND (
                so.docstatus = 1 AND
                so.name LIKE %(txt)s
            ) LIMIT %(start)s, %(page_len)s
        """.format(
            cond=cond,
        ),
        values={
            "station": station,
            "txt": "%%%s%%" % txt,
            "start": start,
            "page_len": page_len,
        },
    )


@frappe.whitelist()
def get_history(name):
    logs = frappe.db.sql(
        """
            SELECT
                sl.posting_datetime,
                sl.station,
                sl.activity,
                lo.on_load_no_of_packages,
                lo.off_load_no_of_packages
            FROM `tabShipping Log` AS sl
            LEFT JOIN `tabLoading Operation` AS lo ON
                lo.name = sl.loading_operation
            WHERE sl.shipping_order = %(shipping_order)s
            ORDER BY sl.posting_datetime
        """,
        values={"shipping_order": name},
        as_dict=1,
    )

    def get_message(log):
        activity = log.get("activity")
        if activity == "Operation":
            on_load = log.get("on_load_no_of_packages")
            off_load = log.get("off_load_no_of_packages")
            msg = (
                " and ".join(
                    filter(
                        None,
                        [
                            on_load and "Loaded {} packages".format(on_load),
                            off_load and "Unloaded {} packages".format(off_load),
                        ],
                    )
                )
                or "Operation"
            )

            return "{} at {}".format(
                msg,
                log.get("station"),
            )

        if activity == "Stopped":
            return "Stopped at {}".format(log.get("station"))

        if activity == "Moving":
            return "Moving to {}".format(log.get("station"))

        return activity

    def get_link(log):
        if log.get("loading_operation"):
            "#Form/Loading Operation/{}".format(log.get("loading_operation"))

        return ""

    def get_event(log):
        return {
            "datetime": log.get("posting_datetime"),
            "status": log.get("activity"),
            "message": get_message(log),
            "link": get_link(log),
        }

    return [get_event(x) for x in logs]


def get_manifest_rows(shipping_order):
    return frappe.db.sql(
        """
            SELECT
                lobo.booking_order,
                lobo.loading_unit,
                lobo.qty,
                SUM(lobo.no_of_packages) AS cur_no_of_packages,
                SUM(lobo.weight_actual) AS cur_weight_actual,
                GROUP_CONCAT(bofd.item_description SEPARATOR ', ') AS item_description,
                bo.destination_station,
                bo.consignor_name,
                bo.consignee_name,
                bo.no_of_packages,
                bo.weight_actual
            FROM `tabLoading Operation Booking Order` AS lobo
            LEFT JOIN `tabLoading Operation` AS lo ON
                lo.name = lobo.parent
            LEFT JOIN `tabBooking Order` AS bo ON
                bo.name = lobo.booking_order
            LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                bofd.name = lobo.bo_detail
            WHERE
                lo.docstatus = 1 AND
                lobo.parentfield = 'on_loads' AND
                lo.shipping_order = %(shipping_order)s
            GROUP BY lobo.booking_order
            ORDER BY lo.name, lobo.idx
        """,
        values={"shipping_order": shipping_order},
        as_dict=1,
    )


def get_freight_summary_rows(shipping_order):
    def get_amount(row):
        rate = row.get("rate") or 0
        if row.get("based_on") == "Packages":
            return (row.get("cur_no_of_packages") or 0) * rate
        if row.get("based_on") == "Weight":
            return (row.get("cur_weight_actual") or 0) * rate
        return row.get("amount") or 0

    freight_rows = frappe.db.sql(
        """
            SELECT
                bo.name AS booking_order,
                bo.consignor_name,
                bo.consignee_name,
                bofd.item_description,
                SUM(lobo.no_of_packages) AS cur_no_of_packages,
                SUM(lobo.weight_actual) AS cur_weight_actual,
                bofd.based_on,
                bofd.rate
            FROM `tabLoading Operation Booking Order` AS lobo
            LEFT JOIN `tabLoading Operation` AS lo ON
                lo.name = lobo.parent
            LEFT JOIN `tabBooking Order` AS bo ON
                bo.name = lobo.booking_order
            LEFT JOIN `tabBooking Order Freight Detail` AS bofd ON
                bofd.name = lobo.bo_detail
            WHERE
                lo.docstatus = 1 AND
                lobo.parentfield = 'on_loads' AND
                lo.shipping_order = %(shipping_order)s
            GROUP BY lobo.name
            ORDER BY lo.name, lobo.idx
        """,
        values={"shipping_order": shipping_order},
        as_dict=1,
    )

    booking_orders = set([x.get("booking_order") for x in freight_rows])

    get_first_loaded_booking_orders = compose(
        list,
        map(lambda x: x.get("booking_order")),
        frappe.db.sql,
    )
    first_loaded_booking_orders = (
        get_first_loaded_booking_orders(
            """
                SELECT
                    lobo.booking_order,
                    lo.shipping_order
                FROM `tabLoading Operation Booking Order` AS lobo
                LEFT JOIN `tabLoading Operation` AS lo ON
                    lo.name = lobo.parent
                LEFT JOIN `tabBooking Order Charge` AS boc ON
                    boc.parent = lobo.booking_order
                WHERE
                    lo.docstatus = 1 AND
                    lobo.parentfield = 'on_loads' AND
                    lobo.booking_order IN %(booking_orders)s
                GROUP by lobo.booking_order
                HAVING lo.shipping_order = %(shipping_order)s
                ORDER BY lo.posting_datetime
            """,
            values={"booking_orders": booking_orders, "shipping_order": shipping_order},
            as_dict=1,
        )
        if booking_orders
        else []
    )

    charges_rows = (
        frappe.db.sql(
            """
                SELECT
                    bo.name AS booking_order,
                    bo.consignor_name,
                    bo.consignee_name,
                    GROUP_CONCAT(boc.charge_type SEPARATOR ', ') AS item_description,
                    0 AS cur_no_of_packages,
                    0 AS cur_weight_actual,
                    '' AS based_on,
                    0 AS rate,
                    SUM(boc.charge_amount) AS amount
                FROM `tabBooking Order` AS bo
                LEFT JOIN `tabBooking Order Charge` AS boc ON
                    boc.parent = bo.name
                WHERE
                    bo.name IN %(booking_orders)s AND
                    boc.charge_amount > 0
                GROUP BY bo.name
            """,
            values={"booking_orders": first_loaded_booking_orders},
            as_dict=1,
        )
        if first_loaded_booking_orders
        else []
    )

    return sorted(
        [merge(x, {"amount": get_amount(x)}) for x in freight_rows + charges_rows],
        key=lambda x: x.get("booking_order"),
    )


@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, posting_datetime=None):
    doc = frappe.get_doc("Shipping Order", source_name)

    def set_invoice_missing_values(source, target):
        target.status = None
        target.supplier = frappe.get_cached_value(
            "Shipping Vendor", doc.shipping_vendor, "supplier"
        )
        target.update(
            frappe.model.utils.get_fetch_values(
                "Purchase Invoice", "supplier", target.supplier
            )
        )
        target.supplier_address = frappe.get_cached_value(
            "Shipping Vendor", doc.shipping_vendor, "primary_address"
        )
        if target.supplier_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Purchase Invoice", "supplier_address", target.supplier_address
                )
            )
        target.taxes_and_charges = None
        target.ignore_pricing_rule = 1
        if doc.start_datetime:
            target.set_posting_time = 1
            dt = frappe.utils.get_datetime(doc.start_datetime)
            target.posting_date = dt.date()
            target.posting_time = dt.time()
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        target.update(get_company_address(target.company))
        if target.company_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Purchase Invoice", "company_address", target.company_address
                )
            )
        

    def postprocess(source, target):
        freight_rates = get_freight_rates()
        loads = get_order_contents(doc).get("on_load")
        target.items = []
        for based_on in ["Packages", "Weight"]:
            freight_item = freight_rates.get(based_on) or {}
            target.append(
                "items",
                {
                    "item_code": freight_item.get("item_code"),
                    "price_list_rate": freight_item.get("rate"),
                    "qty": loads.get(
                        "no_of_packages" if based_on == "Packages" else "weight_actual"
                    ),
                    "rate": 0,
                    "stock_uom": freight_item.get("uom"),
                    "uom": freight_item.get("uom"),
                },
            )

        target.taxes = []
        for charge in doc.charges:
            target.append(
                "taxes",
                {
                    "category": "Total",
                    "add_deduct_tax": "Deduct",
                    "charge_type": "Actual",
                    "account_head": charge.charge_account,
                    "description": charge.item_description,
                    "tax_amount": charge.charge_amount,
                },
            )

        return set_invoice_missing_values(source, target)

    def get_table_maps():
        return {
            "Shipping Order": {
                "doctype": "Purchase Invoice",
                "fieldmap": {"name": "gg_shipping_order"},
                "validation": {"docstatus": ["=", 1]},
            }
        }

    return frappe.model.mapper.get_mapped_doc(
        "Shipping Order", source_name, get_table_maps(), target_doc, postprocess
    )


def get_order_contents(doc):
    params = ["no_of_packages", "weight_actual", "goods_value"]
    fields = list(
        concat(
            [
                ["SUM({t}_{p}) AS {t}_{p}".format(t=t, p=p) for p in params]
                for t in ["on_load", "off_load"]
            ]
        )
    )
    data = frappe.db.sql(
        """
            SELECT {fields} FROM `tabLoading Operation`
            WHERE docstatus = 1 AND shipping_order = %(shipping_order)s
        """.format(
            fields=", ".join(fields)
        ),
        values={"shipping_order": doc.name},
        as_dict=1,
    )[0]

    def get_values(_type):
        fields = list(map(lambda x: "{}_{}".format(_type, x), params))
        _get = compose(
            valmap(lambda x: x or 0),
            keymap(lambda x: x.replace("{}_".format(_type), "")),
            keyfilter(lambda x: x in fields),
        )
        return _get(data)

    on_load = get_values("on_load")
    off_load = get_values("off_load")

    current = merge({}, *[{x: on_load[x] - off_load[x]} for x in params])

    return {
        "on_load": on_load,
        "off_load": off_load,
        "current": current,
    }


@frappe.whitelist()
def get_charges_from_template(template):
    if not template:
        return None

    doc = frappe.get_doc("Shipping Order Charge Template", template)
    if not doc:
        return None

    return [
        {
            "charge_account": x.charge_account,
            "charge_amount": x.charge_amount,
            "item_description": x.item_description,
        }
        for x in doc.charges
    ]