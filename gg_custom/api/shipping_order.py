from __future__ import unicode_literals
import frappe


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
