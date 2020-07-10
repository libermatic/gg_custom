from __future__ import unicode_literals
import frappe
import json
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
