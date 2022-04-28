import frappe


def validate(doc, method):
    if doc.gg_shipping_order and frappe.db.exists(
        "Purchase Invoice",
        {
            "name": ("!=", doc.name),
            "docstatus": 1,
            "gg_shipping_order": doc.gg_shipping_order,
        },
    ):
        frappe.throw(
            frappe._(
                "Purchase Invoice already exists for {}".format(
                    frappe.get_desk_link("Shipping Order", doc.gg_shipping_order)
                )
            )
        )