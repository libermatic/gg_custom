# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

import frappe
from toolz.curried import groupby, compose, concat, concatv, merge


def execute(filters=None):
    columns = _get_columns(filters)
    data = _get_data(filters)
    return columns, data


activities = ["Booked", "Loaded", "Unloaded", "Collected"]


def _get_columns(filters):
    join = compose(list, concatv)
    return join(
        [
            {
                "fieldtype": "Data",
                "fieldname": "item_description",
                "label": "Description",
                "width": 240,
            },
            {
                "fieldtype": "Link",
                "fieldname": "booking_order",
                "options": "Booking Order",
                "label": "Booking Order",
                "width": 120,
            },
            {
                "fieldtype": "Data",
                "fieldname": "consignor_name",
                "label": "Consignor Name",
                "width": 180,
            },
            {
                "fieldtype": "Data",
                "fieldname": "consignee_name",
                "label": "Consignee Name",
                "width": 180,
            },
        ],
        concat(
            [
                {
                    "fieldtype": "Int",
                    "fieldname": "{}__no_of_packages".format(x),
                    "label": "{} Packages".format(x),
                    "width": 90,
                },
                {
                    "fieldtype": "Float",
                    "fieldname": "{}__weight_actual".format(x),
                    "label": "{} Weight".format(x),
                    "width": 90,
                },
            ]
            for x in activities
        ),
    )


def _get_data(filters):
    BookingLog = frappe.qb.DocType("Booking Log")
    BookingOrderFreightDetail = frappe.qb.DocType("Booking Order Freight Detail")
    BookingOrder = frappe.qb.DocType("Booking Order")
    q = (
        frappe.qb.from_(BookingLog)
        .left_join(BookingOrderFreightDetail)
        .on(BookingOrderFreightDetail.name == BookingLog.bo_detail)
        .left_join(BookingOrder)
        .on(BookingOrder.name == BookingLog.booking_order)
        .where(BookingLog.posting_datetime[filters.from_date : filters.to_date])
        .select(
            BookingLog.bo_detail,
            BookingOrderFreightDetail.item_description,
            BookingLog.booking_order,
            BookingOrder.consignor_name,
            BookingOrder.consignee_name,
        )
        .distinct()
        .orderby(BookingLog.posting_datetime)
    )
    if filters.station:
        q = q.where(BookingLog.station == filters.station)
    bo_details = q.run(as_dict=1)

    details = (
        groupby(
            "bo_detail",
            frappe.qb.from_(BookingLog)
            .where(BookingLog.bo_detail.isin([x.bo_detail for x in bo_details]))
            .select(
                BookingLog.booking_order,
                BookingLog.activity,
                BookingLog.no_of_packages,
                BookingLog.weight_actual,
                BookingLog.bo_detail,
            )
            .run(as_dict=1),
        )
        if bo_details
        else {}
    )

    def make_row(row):
        detail = details.get(row.get("bo_detail")) or []
        return merge(
            row,
            {
                "{}__{}".format(activity, qty): sum(
                    [x.get(qty) for x in detail if x.get("activity") == activity]
                )
                for activity in activities
                for qty in ["no_of_packages", "weight_actual"]
            },
        )

    return [make_row(x) for x in bo_details]
