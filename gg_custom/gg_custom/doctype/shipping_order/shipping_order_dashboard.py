from __future__ import unicode_literals
import frappe


def get_data():
    return {
        "fieldname": "shipping_order",
        "non_standard_fieldnames": {
            "Booking Order": "last_shipping_order",
            "Purchase Invoice": "gg_shipping_order",
        },
        "transactions": [
            {"label": "Shipping", "items": ["Loading Operation", "Booking Order"]},
            {"label": "Invoicing", "items": ["Purchase Invoice"]},
        ],
    }
