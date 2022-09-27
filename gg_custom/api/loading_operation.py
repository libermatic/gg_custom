import frappe
from toolz.curried import merge


@frappe.whitelist()
def query(doctype, txt, searchfield, start, page_len, filters):
    fields = [
        "lo.name",
        "lo.shipping_order",
        "lo.vehicle",
    ]
    values = {
        "txt": "%%%s%%" % txt,
        "start": start,
        "page_len": page_len,
    }
    conds = [
        "lo.docstatus = 1",
        "({})".format(" OR ".join(["{} LIKE %(txt)s".format(x) for x in fields])),
        "lobo.parentfield = 'on_loads'",
        "lobo.booking_order = %(booking_order)s",
    ]

    return frappe.db.sql(
        """
            SELECT DISTINCT {fields} FROM `tabLoading Operation` AS lo
            LEFT JOIN `tabLoading Operation Booking Order` AS lobo ON
                lobo.parent = lo.name
            WHERE {conds}
            ORDER BY lo.posting_datetime DESC
            LIMIT %(start)s, %(page_len)s
        """.format(
            fields=", ".join(fields), conds=" AND ".join(conds)
        ),
        values=merge(filters, values),
    )

