from __future__ import unicode_literals
import frappe
import json
from frappe.contacts.doctype.address.address import get_company_address
from toolz.curried import compose, merge, concatv, map, filter


def query(doctype, txt, searchfield, start, page_len, filters):
    _type = filters.get("type")
    fields = [
        "name",
        "source_station",
        "destination_station",
    ]

    values = {
        "station": filters.get("station"),
        "shipping_order": filters.get("shipping_order"),
        "txt": "%%%s%%" % txt,
        "start": start,
        "page_len": page_len,
    }
    if _type == "on_load":
        conds = [
            "docstatus = 1",
            "name LIKE %(txt)s",
            "status IN ('Booked', 'Unloaded')",
            "current_station = %(station)s",
        ]
        return frappe.db.sql(
            """
                SELECT {fields} FROM `tabBooking Order`
                WHERE {conds} LIMIT %(start)s, %(page_len)s
            """.format(
                fields=", ".join(fields), conds=" OR ".join(conds)
            ),
            values=values,
        )
    if _type == "off_load":
        conds = [
            "docstatus = 1",
            "name LIKE %(txt)s",
            "status IN ('Loaded', 'In Transit')",
            "last_shipping_order = %(shipping_order)s",
        ]
        return frappe.db.sql(
            """
                SELECT {fields} FROM `tabBooking Order`
                WHERE {conds} LIMIT %(start)s, %(page_len)s
            """.format(
                fields=", ".join(fields), conds=" AND ".join(conds)
            ),
            values=values,
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


def _get_or_create_customer(booking_order_name, bill_to):
    msg = frappe._("Cannot create Invoice without Customer")
    if not bill_to:
        frappe.throw(msg)

    booking_party_name = frappe.db.get_value(
        "Booking Order", booking_order_name, bill_to
    )
    if not booking_party_name:
        frappe.throw(msg)

    customer_name = frappe.get_cached_value(
        "Booking Party", booking_party_name, "customer"
    )
    if customer_name:
        return customer_name

    customer = create_customer(booking_party_name)
    return customer.name


def create_customer(booking_party_name):
    booking_party = frappe.get_cached_doc("Booking Party", booking_party_name)

    doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": booking_party.booking_party_name,
            "customer_group": frappe.get_cached_value(
                "Selling Settings", None, "customer_group"
            ),
            "territory": frappe.get_cached_value("Selling Settings", None, "territory"),
            "customer_primary_address": booking_party.primary_address,
        }
    ).insert(ignore_permissions=True, ignore_mandatory=True)
    for (parent,) in frappe.get_all(
        "Dynamic Link",
        filters={
            "parenttype": "Address",
            "link_doctype": "Booking Party",
            "link_name": booking_party_name,
        },
        fields=["parent"],
        as_list=1,
    ):
        address = frappe.get_doc("Address", parent)
        address.append("links", {"link_doctype": doc.doctype, "link_name": doc.name})
        address.save()

    frappe.db.set_value("Booking Party", booking_party_name, "customer", doc.name)

    return doc

