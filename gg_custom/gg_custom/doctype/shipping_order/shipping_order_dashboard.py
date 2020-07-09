from __future__ import unicode_literals
import frappe


def get_data():
    return {
        "fieldname": "shipping_order",
        "transactions": [{"label": "Shipping", "items": ["Loading Operation"]}],
    }

