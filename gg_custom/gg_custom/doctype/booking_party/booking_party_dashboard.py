from __future__ import unicode_literals
import frappe


def get_data():
    return {
        "fieldname": "booking_party",
        "non_standard_fieldnames": {"Booking Order": "consignor"},
        "transactions": [{"label": "Shipping", "items": ["Booking Order"]}],
    }

