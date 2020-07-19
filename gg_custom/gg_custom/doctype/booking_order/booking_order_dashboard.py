from __future__ import unicode_literals
import frappe


def get_data():
    return {
        "fieldname": "booking_order",
        "non_standard_fieldnames": {"Sales Invoice": "gg_booking_order"},
        "transactions": [
            {"label": "Shipping", "items": ["Loading Operation"]},
            {"label": "Invoicing", "items": ["Sales Invoice"]},
        ],
    }

