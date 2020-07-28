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

            return "{} at {}".format(msg, log.get("station"),)

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

