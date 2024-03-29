# Copyright (c) 2013, Libermatic and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import IfNull
from erpnext.accounts.report.general_ledger.general_ledger import execute as get_report
from erpnext.accounts.party import get_party_account
from toolz.curried import groupby, valmap, first, compose, merge


def execute(filters=None):
    return _get_columns(filters), _get_data(filters)


def _get_columns(filters):
    return [
        {
            "fieldtype": "Date",
            "fieldname": "posting_date",
            "label": "Posting Date",
            "print_width": 300,
            "width": 90,
        },
        {
            "fieldtype": "Data",
            "fieldname": "voucher_type",
            "label": "Voucher Type",
            "width": 120,
        },
        {
            "fieldtype": "Dynamic Link",
            "fieldname": "voucher_no",
            "options": "voucher_type",
            "label": "Voucher No",
            "width": 180,
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
            "fieldname": "description",
            "label": "Description",
            "width": 300,
        },
        {
            "fieldtype": "Currency",
            "fieldname": "debit",
            "label": "Debit",
            "width": 90,
        },
        {
            "fieldtype": "Currency",
            "fieldname": "credit",
            "label": "Credit",
            "width": 90,
        },
        {
            "fieldtype": "Currency",
            "fieldname": "balance",
            "label": "Balance",
            "width": 90,
        },
        {
            "fieldtype": "Data",
            "fieldname": "paper_receipt_no",
            "label": "Paper Receipt No",
            "width": 90,
        },
        {
            "fieldtype": "Data",
            "fieldname": "order_date",
            "label": "Order Date",
            "width": 90,
        },
        {
            "fieldtype": "Data",
            "fieldname": "delivery_dates",
            "label": "Delivery Dates",
            "width": 150,
        },
        {
            "fieldtype": "Data",
            "fieldname": "consignor",
            "label": "Consignor",
            "width": 180,
        },
        {
            "fieldtype": "Data",
            "fieldname": "consignee",
            "label": "Consignee",
            "width": 180,
        },
    ]


def _get_data(filters):
    company = frappe.db.get_single_value("GG Custom Settings", "company")
    if not company:
        frappe.throw(frappe._("Setup incomplete in GG Custom Settings"))

    customer = frappe.get_cached_value(
        "Booking Party", filters.booking_party, "customer"
    )
    account = get_party_account(
        "Customer",
        customer,
        company,
    )
    _, rows = get_report(
        frappe._dict(
            {
                "from_date": filters.get("from_date"),
                "to_date": filters.get("to_date"),
                "company": company,
                "account": [account],
                "party_type": "Customer",
                "party": [customer],
                "group_by": frappe._("Group by Voucher (Consolidated)"),
            }
        )
    )

    gl_entries = rows[1:-2]

    SalesInvoice = frappe.qb.DocType("Sales Invoice")
    BookingOrder = frappe.qb.DocType("Booking Order")
    invoices = [
        x.get("voucher_no")
        for x in gl_entries
        if x.get("voucher_type") == "Sales Invoice"
    ]
    get_booking_orders = compose(valmap(first), groupby("sales_invoice"))
    booking_orders = (
        get_booking_orders(
            frappe.qb.from_(SalesInvoice)
            .left_join(BookingOrder)
            .on(BookingOrder.name == SalesInvoice.gg_booking_order)
            .where(SalesInvoice.name.isin(invoices))
            .select(
                SalesInvoice.name.as_("sales_invoice"),
                BookingOrder.name,
                BookingOrder.paper_receipt_no,
                BookingOrder.consignor_name.as_("consignor"),
                BookingOrder.consignee_name.as_("consignee"),
                BookingOrder.booking_datetime.as_("order_datetime"),
            )
            .run(as_dict=1)
        )
        if invoices
        else {}
    )

    SalesInvoiceItem = frappe.qb.DocType("Sales Invoice Item")
    BookingOrderFreightDetail = frappe.qb.DocType("Booking Order Freight Detail")
    orders = [v.get("name") for _, v in booking_orders.items()]
    sales_invoice_items = (
        groupby(
            "sales_invoice",
            frappe.qb.from_(SalesInvoiceItem)
            .left_join(BookingOrderFreightDetail)
            .on(BookingOrderFreightDetail.name == SalesInvoiceItem.gg_bo_detail)
            .where(SalesInvoiceItem.parent.isin(invoices))
            .select(
                SalesInvoiceItem.parent.as_("sales_invoice"),
                SalesInvoiceItem.description,
                SalesInvoiceItem.qty,
                SalesInvoiceItem.rate,
                BookingOrderFreightDetail.based_on,
                (IfNull(SalesInvoiceItem.gg_bo_detail, "") != "").as_(
                    "is_freight_item"
                ),
            )
            .run(as_dict=1),
        )
        if invoices
        else {}
    )

    BookingLog = frappe.qb.DocType("Booking Log")
    get_delivery_dates = groupby("booking_order")
    delivery_dates = (
        get_delivery_dates(
            frappe.qb.from_(BookingLog)
            .where(
                (BookingLog.activity == "Collected")
                & (BookingLog.booking_order.isin(orders))
            )
            .select(BookingLog.booking_order, BookingLog.posting_datetime)
            .run(as_dict=1)
        )
        if orders
        else {}
    )

    def make_message(item):
        rate = frappe.utils.fmt_money(
            item.get("rate"), currency=frappe.defaults.get_global_default("currency")
        )

        if item.get("is_freight_item"):
            if item.get("based_on") == "Weight":
                return "{} by weight @ {} - {}".format(
                    item.get("qty"), rate, item.get("description")
                )

            if item.get("based_on") == "Packages":
                return "{} packages @ {} - {}".format(
                    item.get("qty"), rate, item.get("description")
                )

        return "{} @ {}".format(item.get("description"), rate)

    def make_description(si):
        return "<br />".join(
            [
                make_message(x)
                for x in sales_invoice_items.get(si, [])
                if x.get("qty") and x.get("rate")
            ]
        )

    def make_delivery_date(bo):
        return ", ".join(
            set(
                [
                    frappe.format_value(
                        x.get("posting_datetime"), {"fieldtype": "Date"}
                    )
                    for x in delivery_dates.get(bo, [])
                ]
            )
        )

    def make_row(row):
        booking_order = booking_orders.get(row.get("voucher_no"), {})
        bo_name = booking_order.get("name")
        order_date = booking_order.get("order_datetime")
        return merge(
            row,
            {
                "booking_order": bo_name,
                "paper_receipt_no": booking_order.get("paper_receipt_no"),
                "description": make_description(row.get("voucher_no"))
                if row.get("voucher_type") == "Sales Invoice"
                else (row.remarks.split("\n")[0] if row.get("remarks") else ""),
                "consignor": booking_order.get("consignor"),
                "consignee": booking_order.get("consignee"),
                "order_date": frappe.format_value(order_date, {"fieldtype": "Date"})
                if order_date
                else "",
                "delivery_dates": make_delivery_date(bo_name),
            },
        )

    def make_ag_row(row, label):
        return merge(row, {"voucher_type": label})

    return (
        [make_ag_row(rows[0], "Opening")]
        + [make_row(x) for x in gl_entries]
        + [make_ag_row(rows[-2], "Total"), make_ag_row(rows[-1], "Closing")]
    )
