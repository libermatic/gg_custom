from __future__ import unicode_literals
import frappe
import json
from toolz.curried import compose, merge, concatv, map, filter


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
    get_changes = compose(
        merge,
        map(lambda x: {x[0]: x[2]}),
        filter(lambda x: x[0] in ["status", "current_station", "next_station"]),
        lambda x: x.get("changed", []),
        json.loads,
        lambda x: x.get("data"),
    )

    def get_version_message(version):
        changes = version.get("changes")
        if changes.get("status") == "Stopped":
            return "Stopped at {}".format(changes.get("current_station") or "Station")
        if changes.get("status") == "In Transit":
            return "Moving to {}".format(changes.get("next_station") or "Station")
        return changes.get("status")

    get_versions = compose(
        map(
            lambda x: {
                "datetime": x.get("creation"),
                "status": x.get("changes").get("status"),
                "message": get_version_message(x),
            }
        ),
        filter(lambda x: x.get("changes")),
        map(lambda x: merge(x, {"changes": get_changes(x)})),
        lambda x: frappe.get_all(
            "Version",
            filters={"ref_doctype": "Shipping Order", "docname": x},
            fields=["creation", "data"],
        ),
    )

    def get_loading_message(loading):
        return "Loaded {} bookings and unloaded {} bookings at {}".format(
            loading.get("on_load_no_of_bookings"),
            loading.get("off_load_no_of_bookings"),
            loading.get("station"),
        )

    get_loadings = compose(
        map(
            lambda x: {
                "datetime": x.get("posting_datetime"),
                "message": get_loading_message(x),
                "status": "Operation",
                "link": "#Form/Loading Operation/{}".format(x.get("name")),
            }
        ),
        lambda x: frappe.get_all(
            "Loading Operation",
            filters={"docstatus": 1, "shipping_order": x},
            fields=[
                "name",
                "station",
                "posting_datetime",
                "on_load_no_of_bookings",
                "off_load_no_of_bookings",
            ],
        ),
    )

    return sorted(
        concatv(get_versions(name), get_loadings(name)),
        key=lambda x: frappe.utils.get_datetime(x.get("datetime")),
    )

