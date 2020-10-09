from __future__ import unicode_literals
import frappe


def validate(doc, method):
    if doc.gg_freight_based_on:
        existing = frappe.db.exists(
            "Item",
            {"name": ("!=", doc.name), "gg_freight_based_on": doc.gg_freight_based_on},
        )
        if existing:
            frappe.throw(
                frappe._(
                    "{} is already defined as a freight Item based on {}".format(
                        existing, doc.gg_freight_based_on
                    )
                )
            )

