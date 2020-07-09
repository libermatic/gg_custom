from __future__ import unicode_literals
import frappe


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
