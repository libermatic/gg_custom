import frappe
from toolz.curried import merge

from gg_custom.api.booking_party import update_customer


def execute():
    for (name,) in frappe.db.sql(
        """
            SELECT bp.name
            FROM `tabBooking Party` AS bp
            LEFT JOIN `tabCustomer` AS c ON
                c.name = bp.customer
            WHERE
                bp.booking_party_name != c.customer_name OR
                bp.primary_address != c.customer_primary_address
        """
    ):
        update_customer(name)

