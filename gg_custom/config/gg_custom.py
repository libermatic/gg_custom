from __future__ import unicode_literals
import frappe


def get_data():
    return [
        {
            "label": frappe._("Booking"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Booking Order",
                    "description": frappe._("Booking Order"),
                },
                {
                    "type": "doctype",
                    "name": "Booking Party",
                    "description": frappe._("Consignor / Consignee Details"),
                },
            ],
        },
        {
            "label": frappe._("Shipping"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Shipping Order",
                    "description": frappe._("Shipping Order"),
                },
                {
                    "type": "doctype",
                    "name": "Loading Operation",
                    "description": frappe._("Loading Operation"),
                },
                {
                    "type": "doctype",
                    "name": "Vehicle",
                    "description": frappe._("Vehicle"),
                },
            ],
        },
        {
            "label": frappe._("Setup"),
            "items": [
                {
                    "type": "doctype",
                    "name": "Driver",
                    "description": frappe._("Driver Detals"),
                },
                {
                    "type": "doctype",
                    "name": "Item",
                    "description": frappe._("Items used as Booking Charge"),
                },
                {
                    "type": "doctype",
                    "name": "Booking Order Charge Template",
                    "description": frappe._("Booking Order Charge Template"),
                },
                {
                    "type": "doctype",
                    "name": "Station",
                    "description": frappe._("Station"),
                },
            ],
        },
    ]
