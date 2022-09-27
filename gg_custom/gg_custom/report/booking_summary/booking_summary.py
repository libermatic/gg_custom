# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

import frappe
from toolz.curried import groupby, compose, concat, concatv, merge


def execute(filters=None):
    columns = _get_columns(filters)
    keys = [x.get("fieldname") for x in columns]
    clauses, values = _get_filters(filters)
    data = _get_data(clauses, values, keys)
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


def _get_filters(filters):
    join = compose(lambda x: " AND ".join(x), concatv)
    clauses = join(
        ["bl.posting_datetime BETWEEN %(from_date)s AND %(to_date)s"],
        ["bl.station = %(station)s"] if filters.station else [],
    )

    return clauses, filters


def _get_data(clauses, values, keys):
    bo_details = frappe.db.sql(
        """
            SELECT
                DISTINCT bl.bo_detail,
                bofd.item_description,
                bl.booking_order,
                bo.consignor_name,
                bo.consignee_name
            FROM `tabBooking Log` AS bl
            LEFT JOIN `tabBooking Order Freight Detail` AS bofd
                ON bofd.name = bl.bo_detail
            LEFT JOIN `tabBooking Order` AS bo
                ON bo.name = bl.booking_order
            WHERE {clauses} ORDER BY bl.posting_datetime
        """.format(
            clauses=clauses
        ),
        values=values,
        as_dict=1,
    )

    details = (
        groupby(
            "bo_detail",
            frappe.db.sql(
                """
                    SELECT
                        booking_order,
                        activity,
                        no_of_packages,
                        weight_actual,
                        bo_detail
                    FROM `tabBooking Log`
                    WHERE bo_detail IN %(bo_details)s
                """,
                values={"bo_details": [x.bo_detail for x in bo_details]},
                as_dict=1,
            ),
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

