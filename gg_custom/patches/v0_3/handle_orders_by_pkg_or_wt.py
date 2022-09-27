import frappe
from toolz.curried import merge


def execute():
    _set_freight_in_booking_orders()
    _update_loading_operation()
    _update_booking_log()


def _set_freight_in_booking_orders():
    freight = frappe.db.sql(
        """
            SELECT
                boc.name,
                bo.creation,
                bo.modified,
                bo.modified_by,
                bo.owner,
                bo.docstatus,
                bo.name AS parent,
                'freight' AS parentfield,
                'Booking Order' AS parenttype,
                1 AS idx,
                'Packages' AS based_on,
                bo.item_description,
                bo.no_of_packages AS qty,
                boc.charge_amount / bo.no_of_packages AS rate,
                boc.charge_amount AS amount
            FROM `tabBooking Order Charge` AS boc
            LEFT JOIN `tabBooking Order` AS bo ON
                bo.name = boc.parent
            WHERE boc.charge_type = 'Freight'
        """,
        as_dict=1,
    )

    for row in freight:
        _insert_freight(
            merge(
                row, {"name": frappe.generate_hash("Booking Order Freight Detail", 10)}
            )
        )

    for row in freight:
        _remove_freight_from_charges(row.get("name"))


def _insert_freight(doc):
    try:
        frappe.db.sql(
            """
                INSERT INTO `tabBooking Order Freight Detail` ({fields}) VALUES ({values})
            """.format(
                fields=", ".join(doc.keys()),
                values=", ".join(["%({})s".format(x) for x in doc.keys()]),
            ),
            values=doc,
        )
    except Exception as e:
        if frappe.db.is_primary_key_violation(e):
            _insert_freight(
                merge(
                    doc,
                    {"name": frappe.generate_hash("Booking Order Freight Detail", 10)},
                )
            )
            return


def _remove_freight_from_charges(name):
    frappe.delete_doc("Booking Order Charge", name, force=1, for_reload=True)


def _update_loading_operation():
    frappe.db.sql(
        """
            UPDATE `tabLoading Operation Booking Order`
            SET loading_unit = 'Packages', qty = no_of_packages
            WHERE loading_unit IS NULL
        """
    )


def _update_booking_log():
    frappe.db.sql(
        """
            UPDATE `tabBooking Log` SET loading_unit = 'Packages'
            WHERE activity != 'Booked' AND loading_unit IS NULL
        """
    )
