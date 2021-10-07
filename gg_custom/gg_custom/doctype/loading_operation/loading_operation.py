# -*- coding: utf-8 -*-
# pylint:disable=no-member
# Copyright (c) 2020, Libermatic and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from gg_custom.doc_events.sales_invoice import validate_invoice
import frappe
from frappe.model.document import Document
from toolz.curried import compose, valmap, first, groupby

from gg_custom.api.booking_order import (
    get_orders_for,
    get_loading_conversion_factor,
    make_sales_invoice,
)


class LoadingOperation(Document):
    def validate(self):
        if self._action == "submit" and not self.on_loads and not self.off_loads:
            frappe.throw(
                frappe._(
                    "Cannot submit without any on or off loads.Please make sure "
                    "at least one of On Load and Off Load tables are not empty."
                )
            )

        self._validate_shipping_order()
        self._validate_booking_orders()
        self._validate_invoice_params()

    @frappe.whitelist()
    def get_on_loads(self):
        self.on_loads = []
        for booking_order in get_orders_for(station=self.station):
            self.append("on_loads", booking_order)

    @frappe.whitelist()
    def get_off_loads(self):
        self._validate_shipping_order()

        self.off_loads = []
        for booking_order in get_orders_for(shipping_order=self.shipping_order):
            self.append("off_loads", booking_order)

    def before_save(self):
        for load in self.on_loads + self.off_loads:
            no_of_packages, weight_actual = frappe.get_cached_value(
                "Booking Order Freight Detail",
                load.bo_detail,
                ["no_of_packages", "weight_actual"],
            )
            conversion_factor = get_loading_conversion_factor(
                load.qty, load.loading_unit, no_of_packages, weight_actual
            )
            if not conversion_factor:
                frappe.throw(frappe._("Invalid conversion in row {}".format(load.idx)))

            load.no_of_packages = frappe.utils.rounded(
                no_of_packages * conversion_factor,
                precision=load.precision("no_of_packages"),
            )
            load.weight_actual = frappe.utils.rounded(
                weight_actual * conversion_factor,
                precision=load.precision("weight_actual"),
            )

        for param in ["no_of_packages", "weight_actual"]:
            for direction in ["on_load", "off_load"]:
                field = "{}_{}".format(direction, param)
                table = self.get("{}s".format(direction))
                self.set(field, sum([x.get(param) for x in table]))

        self.on_load_no_of_bookings = len(self.on_loads)
        self.off_load_no_of_bookings = len(self.off_loads)

    def on_submit(self):
        frappe.enqueue(_create_logs_and_set_statuses, doc=self)
        _create_sales_invoices(self)

    def before_cancel(self):
        self._validate_shipping_order()
        self._validate_collected_booking_orders()
        self._validate_paid_booking_orders()

    def on_cancel(self):
        self.ignore_linked_doctypes = ["Sales Invoice"]
        frappe.enqueue(_remove_logs_and_set_statuses, doc=self)
        _cancel_sales_invoices(self)

    @frappe.whitelist()
    def remove_booking_orders(self, booking_orders):
        if len(booking_orders) == len(self.on_loads):
            frappe.throw(frappe._("Cannot remove all Booking Orders"))

        for row in booking_orders:
            for (name,) in frappe.get_all(
                "Booking Log",
                filters={
                    "loading_operation": self.name,
                    "bo_detail": row.get("bo_detail"),
                },
                as_list=1,
            ):
                frappe.delete_doc("Booking Log", name, ignore_permissions=True)

            for (name,) in frappe.get_all(
                "Sales Invoice Item",
                fields=["parent"],
                filters={
                    "docstatus": 1,
                    "gg_bo_detail": row.get("bo_detail"),
                },
                as_list=1,
            ):
                if (
                    frappe.get_cached_value(
                        "Sales Invoice", name, "gg_loading_operation"
                    )
                    == self.name
                ):
                    invoice = frappe.get_doc("Sales Invoice", name)
                    invoice.flags.ignore_permissions = True
                    invoice.cancel()

        to_remove = [x.get("name") for x in booking_orders]
        for row in self.on_loads:
            if row.name in to_remove:
                self.on_loads.remove(row)

        for param in ["no_of_packages", "weight_actual"]:
            self.set(
                "on_load_{}".format(param), sum([x.get(param) for x in self.on_loads])
            )
        self.on_load_no_of_bookings = len(self.on_loads)
        self.flags.ignore_validate_update_after_submit = True
        self.save()

    def _validate_shipping_order(self):
        """disable validation"""
        # status, current_station = frappe.db.get_value(
        #     "Shipping Order", self.shipping_order, ["status", "current_station"]
        # )
        # if status != "Stopped" or current_station != self.station:
        #     frappe.throw(
        #         frappe._(
        #             "Operation can only be performed for a Shipping Order {} at {}".format(
        #                 frappe.bold("stopped"),
        #                 frappe.get_desk_link("Station", current_station)
        #                 if current_station
        #                 else frappe.bold("Station"),
        #             )
        #         )
        #     )

    def _validate_collected_booking_orders(self):
        for bo_name in set(x.booking_order for x in self.on_loads + self.off_loads):
            status = frappe.get_cached_value("Booking Order", bo_name, "status")
            if status == "Collected":
                frappe.throw(
                    frappe._(
                        "Cannot cancel this Loading Operation contains "
                        "{} which is already Collected.".format(
                            frappe.get_desk_link("Booking Order", bo_name)
                        )
                    )
                )

    def _validate_paid_booking_orders(self):
        if "System Manager" in frappe.get_roles():
            return

        bos = list(set(x.booking_order for x in self.on_loads))
        if bos:
            paid_invoice_count = frappe.db.sql(
                """
                    SELECT COUNT(per.reference_name) FROM `tabPayment Entry Reference` AS per
                    LEFT JOIN `tabPayment Entry` AS pe ON pe.name = per.parent
                    LEFT JOIN `tabSales Invoice` AS si ON si.name = per.reference_name
                    WHERE
                        pe.docstatus = 1 AND
                        per.reference_doctype = 'Sales Invoice' AND
                        si.gg_booking_order IN %(bos)s
                """,
                values={"bos": bos},
            )[0][0]
            if paid_invoice_count:
                frappe.throw(
                    frappe._(
                        "Cannot cancel this Loading Operation because it contains paid Booking Orders"
                    )
                )

    def _validate_booking_orders(self):
        rows_with_zero_qty = [
            x.booking_order for x in self.on_loads + self.off_loads if x.qty <= 0
        ]
        if rows_with_zero_qty:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} cannot contain zero or less qty".format(
                        ", ".join(rows_with_zero_qty)
                    )
                )
            )

        self._validate_dupe_bo("on_loads")
        self._validate_dupe_bo("off_loads")

        get_map = compose(valmap(first), groupby("bo_detail"))

        def check_qty(orders, row):
            if row.get("loading_unit") == "Weight":
                return row.qty > orders.get(row.bo_detail, {}).get("weight_actual", 0)
            return row.qty > orders.get(row.bo_detail, {}).get("no_of_packages", 0)

        on_loads_orders = get_map(get_orders_for(station=self.station))
        on_load_rows_with_invalid_qty = [
            x.booking_order for x in self.on_loads if check_qty(on_loads_orders, x)
        ]
        if on_load_rows_with_invalid_qty:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} contain invalid no of qty".format(
                        ", ".join(on_load_rows_with_invalid_qty)
                    )
                )
            )

        off_loads_orders = get_map(get_orders_for(shipping_order=self.shipping_order))
        off_load_rows_with_invalid_qty = [
            x.booking_order for x in self.off_loads if check_qty(off_loads_orders, x)
        ]
        if off_load_rows_with_invalid_qty:
            frappe.throw(
                frappe._(
                    "Booking Orders: {} contain invalid no of qty".format(
                        ", ".join(off_load_rows_with_invalid_qty)
                    )
                )
            )

    def _validate_dupe_bo(self, field):
        rows = [x.bo_detail for x in self.get(field, [])]
        dupes = [x for x in set(rows) if len([y for y in rows if y == x]) > 1]
        if dupes:
            frappe.throw(
                frappe._(
                    "Duplicate Booking Orders with same Freight Detail found in rows # {}".format(
                        ", ".join(
                            [
                                frappe.utils.cstr(row.idx)
                                for row in self.get(field)
                                if row.bo_detail in dupes
                            ]
                        )
                    )
                )
            )

    def _validate_invoice_params(self):
        for booking_order, items in groupby(
            "booking_order", [x.as_dict() for x in self.on_loads]
        ).items():
            if len(set([x.get("auto_bill_to") for x in items])) > 1:
                frappe.throw(
                    frappe._(
                        "Invalid Auto Bill To selected in rows # {} for Booking Order {}".format(
                            ", ".join([frappe.utils.cstr(x.get("idx")) for x in items]),
                            booking_order,
                        )
                    )
                )

        errors = []
        for item in [x for x in self.on_loads if x.auto_bill_to]:
            frappe.flags.args = {
                "bill_to": item.auto_bill_to.lower(),
                "taxes_and_charges": None,
                "is_freight_invoice": 1,
                "loading_operation": self.name,
            }
            invoice = make_sales_invoice(
                item.booking_order, posting_datetime=self.posting_datetime
            )
            invoice.flags.validate_loading = True
            msg = validate_invoice(invoice, throw=False)
            if msg:
                errors.append(msg)
        if errors:
            frappe.throw(errors)


def _create_logs_and_set_statuses(doc):
    def create_log(load):
        if load.parentfield not in ["on_loads", "off_loads"]:
            frappe.throw(frappe._("Invalid Loading Operation load"))

        activity = "Loaded" if load.parentfield == "on_loads" else "Unloaded"
        direction = -1 if load.parentfield == "on_loads" else 1
        frappe.get_doc(
            {
                "doctype": "Booking Log",
                "posting_datetime": doc.posting_datetime,
                "booking_order": load.booking_order,
                "shipping_order": doc.shipping_order,
                "station": doc.station,
                "activity": activity,
                "loading_operation": doc.name,
                "loading_unit": load.loading_unit,
                "no_of_packages": direction * load.no_of_packages,
                "weight_actual": direction * load.weight_actual,
                "bo_detail": load.bo_detail,
            }
        ).insert(ignore_permissions=True)

    for load in doc.on_loads + doc.off_loads:
        create_log(load)

    for load in doc.on_loads:
        bo = frappe.get_cached_doc("Booking Order", load.booking_order)
        if bo.status == "Booked":
            bo.status = "In Progress"
            bo.save(ignore_permissions=True)

    frappe.get_doc(
        {
            "doctype": "Shipping Log",
            "posting_datetime": doc.posting_datetime,
            "shipping_order": doc.shipping_order,
            "station": doc.station,
            "activity": "Operation",
            "loading_operation": doc.name,
        }
    ).insert(ignore_permissions=True)


def _remove_logs_and_set_statuses(doc):
    for log_type in ["Booking Log", "Shipping Log"]:
        for (log_name,) in frappe.get_all(
            log_type, filters={"loading_operation": doc.name}, as_list=1
        ):
            frappe.delete_doc(log_type, log_name, ignore_permissions=True)

    for load in doc.on_loads:
        bo = frappe.get_cached_doc("Booking Order", load.booking_order)
        if bo.status == "In Progress" and not frappe.db.exists(
            "Booking Log",
            {
                "booking_order": bo.name,
                "activity": "Loaded",
                "loading_operation": ("!=", doc.name),
            },
        ):
            bo.status = "Booked"
            bo.save(ignore_permissions=True)


def _create_sales_invoices(doc):
    booking_orders = set(
        [(x.booking_order, x.auto_bill_to) for x in doc.on_loads if x.auto_bill_to]
    )
    for booking_order, auto_bill_to in booking_orders:
        frappe.flags.args = {
            "bill_to": auto_bill_to.lower(),
            "taxes_and_charges": None,
            "is_freight_invoice": 1,
            "loading_operation": doc.name,
        }
        invoice = make_sales_invoice(
            booking_order, posting_datetime=doc.posting_datetime
        )
        invoice.flags.skip_validation = True
        invoice.insert(ignore_permissions=True)
        invoice.submit()


def _cancel_sales_invoices(doc):
    for (name,) in frappe.get_all(
        "Sales Invoice",
        filters={"docstatus": 1, "gg_loading_operation": doc.name},
        as_list=1,
    ):
        invoice = frappe.get_doc("Sales Invoice", name)
        invoice.flags.ignore_permissions = True
        invoice.cancel()
        frappe.delete_doc(
            "Sales Invoice",
            name,
            flags={"ignore_links": True},
            ignore_permissions=True,
        )
