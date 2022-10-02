import frappe
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Sum, GroupConcat
from toolz.curried import (
    compose,
    merge,
    valmap,
    keymap,
    keyfilter,
    unique,
    map,
    filter,
)
from frappe.contacts.doctype.address.address import get_company_address

from gg_custom.api.booking_order import (
    get_freight_rates,
    get_payment_entry_from_invoices,
)


@frappe.whitelist()
def query(doctype, txt, searchfield, start, page_len, filters):
    ShippingOrder = frappe.qb.DocType("Shipping Order")
    ShippingOrderTransitStation = frappe.qb.DocType("Shipping Order Transit Station")

    q = (
        frappe.qb.from_(ShippingOrder)
        .left_join(ShippingOrderTransitStation)
        .on(ShippingOrderTransitStation.parent == ShippingOrder.name)
        .where(ShippingOrder.docstatus == 1)
        .where(ShippingOrder.name.like(f"%{txt}%"))
        .select(
            ShippingOrder.name,
            ShippingOrder.vehicle,
            ShippingOrder.driver_name,
            ShippingOrder.driver,
        )
        .distinct()
        .limit(page_len)
        .offset(start)
    )
    station = filters.get("station")
    if station:
        q = q.where(
            Criterion.any(
                [
                    ShippingOrder.initial_station == station,
                    ShippingOrder.final_station == station,
                    ShippingOrderTransitStation.station == station,
                ]
            )
        )

    return q.run()


@frappe.whitelist()
def get_history(name):
    ShippingLog = frappe.qb.DocType("Shipping Log")
    LoadingOperation = frappe.qb.DocType("Loading Operation")

    logs = (
        frappe.qb.from_(ShippingLog)
        .left_join(LoadingOperation)
        .on(LoadingOperation.name == ShippingLog.loading_operation)
        .where(ShippingLog.shipping_order == name)
        .select(
            ShippingLog.posting_datetime,
            ShippingLog.station,
            ShippingLog.activity,
            LoadingOperation.on_load_no_of_packages,
            LoadingOperation.off_load_no_of_packages,
        )
        .orderby(ShippingLog.posting_datetime)
    ).run(as_dict=1)

    def get_message(log):
        activity = log.get("activity")
        if activity == "Operation":
            on_load = log.get("on_load_no_of_packages")
            off_load = log.get("off_load_no_of_packages")
            msg = (
                " and ".join(
                    filter(
                        None,
                        [
                            on_load and "Loaded {} packages".format(on_load),
                            off_load and "Unloaded {} packages".format(off_load),
                        ],
                    )
                )
                or "Operation"
            )

            return "{} at {}".format(
                msg,
                log.get("station"),
            )

        if activity == "Stopped":
            return "Stopped at {}".format(log.get("station"))

        if activity == "Moving":
            return "Moving to {}".format(log.get("station"))

        return activity

    def get_link(log):
        if log.get("loading_operation"):
            "#Form/Loading Operation/{}".format(log.get("loading_operation"))

        return ""

    def get_event(log):
        return {
            "datetime": log.get("posting_datetime"),
            "status": log.get("activity"),
            "message": get_message(log),
            "link": get_link(log),
        }

    return [get_event(x) for x in logs]


def get_manifest_rows(shipping_order):
    LoadingOperationBookingOrder = frappe.qb.DocType("Loading Operation Booking Order")
    LoadingOperation = frappe.qb.DocType("Loading Operation")
    BookingOrder = frappe.qb.DocType("Booking Order")
    BookingOrderFreightDetail = frappe.qb.DocType("Booking Order Freight Detail")

    return (
        frappe.qb.from_(LoadingOperationBookingOrder)
        .left_join(LoadingOperation)
        .on(LoadingOperation.name == LoadingOperationBookingOrder.parent)
        .left_join(BookingOrder)
        .on(BookingOrder.name == LoadingOperationBookingOrder.booking_order)
        .left_join(BookingOrderFreightDetail)
        .on(BookingOrderFreightDetail.name == LoadingOperationBookingOrder.bo_detail)
        .where(
            (LoadingOperation.docstatus == 1)
            & (LoadingOperationBookingOrder.parentfield == "on_loads")
        )
        .where(LoadingOperation.shipping_order == shipping_order)
        .select(
            LoadingOperationBookingOrder.booking_order,
            LoadingOperationBookingOrder.loading_unit,
            LoadingOperationBookingOrder.qty,
            Sum(LoadingOperationBookingOrder.no_of_packages, "cur_no_of_packages"),
            Sum(LoadingOperationBookingOrder.weight_actual, "cur_weight_actual"),
            GroupConcat(BookingOrderFreightDetail.item_description, "item_description"),
            BookingOrder.destination_station,
            BookingOrder.consignor_name,
            BookingOrder.consignee_name,
            BookingOrder.no_of_packages,
            BookingOrder.weight_actual,
        )
        .groupby(LoadingOperationBookingOrder.booking_order)
        .orderby(LoadingOperation.name)
        .orderby(LoadingOperation.idx)
    ).run(as_dict=1)


def get_freight_summary_rows(shipping_order):
    def get_amount(row):
        rate = row.get("rate") or 0
        if row.get("based_on") == "Packages":
            return (row.get("cur_no_of_packages") or 0) * rate
        if row.get("based_on") == "Weight":
            return (row.get("cur_weight_actual") or 0) * rate
        return row.get("amount") or 0

    LoadingOperationBookingOrder = frappe.qb.DocType("Loading Operation Booking Order")
    LoadingOperation = frappe.qb.DocType("Loading Operation")
    BookingOrder = frappe.qb.DocType("Booking Order")
    BookingOrderFreightDetail = frappe.qb.DocType("Booking Order Freight Detail")
    BookingOrderCharge = frappe.qb.DocType("Booking Order Charge")

    freight_rows = (
        frappe.qb.from_(LoadingOperationBookingOrder)
        .left_join(LoadingOperation)
        .on(LoadingOperation.name == LoadingOperationBookingOrder.parent)
        .left_join(BookingOrder)
        .on(BookingOrder.name == LoadingOperationBookingOrder.booking_order)
        .left_join(BookingOrderFreightDetail)
        .on(BookingOrderFreightDetail.name == LoadingOperationBookingOrder.bo_detail)
        .where(
            (LoadingOperation.docstatus == 1)
            & (LoadingOperationBookingOrder.parentfield == "on_loads")
        )
        .where(LoadingOperation.shipping_order == shipping_order)
        .select(
            BookingOrder.name.as_("booking_order"),
            BookingOrder.consignor_name,
            BookingOrder.consignee_name,
            BookingOrderFreightDetail.item_description,
            Sum(LoadingOperationBookingOrder.no_of_packages, "cur_no_of_packages"),
            Sum(LoadingOperationBookingOrder.weight_actual, "cur_weight_actual"),
            BookingOrderFreightDetail.based_on,
            BookingOrderFreightDetail.rate,
        )
        .groupby(LoadingOperationBookingOrder.name)
        .orderby(LoadingOperation.name)
        .orderby(LoadingOperationBookingOrder.idx)
    ).run(as_dict=1)

    booking_orders = set([x.get("booking_order") for x in freight_rows])

    first_loaded_booking_orders = (
        [
            x.get("booking_order")
            for x in (
                frappe.qb.from_(LoadingOperationBookingOrder)
                .left_join(LoadingOperation)
                .on(LoadingOperation.name == LoadingOperationBookingOrder.parent)
                .left_join(BookingOrderCharge)
                .on(
                    BookingOrderCharge.parent
                    == LoadingOperationBookingOrder.booking_order
                )
                .where(
                    (LoadingOperation.docstatus == 1)
                    & (LoadingOperationBookingOrder.parentfield == "on_loads")
                )
                .where(LoadingOperationBookingOrder.booking_order.isin(booking_orders))
                .select(
                    LoadingOperationBookingOrder.booking_order,
                    LoadingOperation.shipping_order,
                )
                .groupby(LoadingOperationBookingOrder.booking_order)
                .having(LoadingOperation.shipping_order == shipping_order)
                .orderby(LoadingOperation.posting_datetime)
            ).run(as_dict=1)
        ]
        if booking_orders
        else []
    )

    charges_rows = (
        [
            {
                **x,
                "cur_no_of_packages": 0,
                "cur_weight_actual": 0,
                "based_on": "",
                "rate": 0,
            }
            for x in (
                (
                    frappe.qb.from_(BookingOrder)
                    .left_join(BookingOrderCharge)
                    .on(BookingOrderCharge.parent == BookingOrder.name)
                    .where(BookingOrder.name.isin(first_loaded_booking_orders))
                    .where(BookingOrderCharge.charge_amount > 0)
                    .select(
                        BookingOrder.name.as_("booking_order"),
                        BookingOrder.consignor_name,
                        BookingOrder.consignee_name,
                        GroupConcat(BookingOrderCharge.charge_type, "item_description"),
                        Sum(BookingOrderCharge.charge_amount, "amount"),
                    )
                    .groupby(BookingOrder.name)
                )
            ).run(as_dict=1)
        ]
        if first_loaded_booking_orders
        else []
    )

    return sorted(
        [{**x, "amount": get_amount(x)} for x in freight_rows + charges_rows],
        key=lambda x: x.get("booking_order"),
    )


@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, posting_datetime=None):
    doc = frappe.get_doc("Shipping Order", source_name)

    def set_invoice_missing_values(source, target):
        target.status = None
        target.supplier = doc.transporter
        target.update(
            frappe.model.utils.get_fetch_values(
                "Purchase Invoice", "supplier", target.supplier
            )
        )
        target.supplier_address = frappe.get_cached_value(
            "Supplier", doc.transporter, "supplier_primary_address"
        )
        if target.supplier_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Purchase Invoice", "supplier_address", target.supplier_address
                )
            )
        target.taxes_and_charges = None
        target.ignore_pricing_rule = 1
        if doc.start_datetime:
            target.set_posting_time = 1
            dt = frappe.utils.get_datetime(doc.start_datetime)
            target.posting_date = dt.date()
            target.posting_time = dt.time()
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")
        target.update(get_company_address(target.company))
        if target.company_address:
            target.update(
                frappe.model.utils.get_fetch_values(
                    "Purchase Invoice", "company_address", target.company_address
                )
            )

    def postprocess(source, target):
        freight_rates = get_freight_rates()
        loads = get_order_contents(doc).get("on_load")
        target.items = []
        for based_on in ["Packages", "Weight"]:
            freight_item = freight_rates.get(based_on) or {}
            target.append(
                "items",
                {
                    "item_code": freight_item.get("item_code"),
                    "price_list_rate": freight_item.get("rate"),
                    "qty": loads.get(
                        "no_of_packages" if based_on == "Packages" else "weight_actual"
                    ),
                    "rate": 0,
                    "stock_uom": freight_item.get("uom"),
                    "uom": freight_item.get("uom"),
                },
            )

        target.taxes = []
        for charge in doc.charges:
            target.append(
                "taxes",
                {
                    "category": "Total",
                    "add_deduct_tax": "Deduct",
                    "charge_type": "Actual",
                    "account_head": charge.charge_account,
                    "description": charge.item_description,
                    "tax_amount": charge.charge_amount,
                },
            )

        return set_invoice_missing_values(source, target)

    def get_table_maps():
        return {
            "Shipping Order": {
                "doctype": "Purchase Invoice",
                "fieldmap": {"name": "gg_shipping_order"},
                "validation": {"docstatus": ["=", 1]},
            }
        }

    return frappe.model.mapper.get_mapped_doc(
        "Shipping Order", source_name, get_table_maps(), target_doc, postprocess
    )


def get_order_contents(doc):
    LoadingOperation = frappe.qb.DocType("Loading Operation")
    params = ["no_of_packages", "weight_actual", "goods_value"]
    fieldnames = [f"{t}_{p}" for p in params for t in ["on_load", "off_load"]]
    data = (
        frappe.qb.from_(LoadingOperation)
        .where(LoadingOperation.docstatus == 1)
        .where(LoadingOperation.shipping_order == doc.name)
        .select(
            *[Sum(LoadingOperation[x]).as_(x) for x in fieldnames],
        )
    ).run(as_dict=1)[0]

    def get_values(_type):
        fields = list(map(lambda x: "{}_{}".format(_type, x), params))
        _get = compose(
            valmap(lambda x: x or 0),
            keymap(lambda x: x.replace("{}_".format(_type), "")),
            keyfilter(lambda x: x in fields),
        )
        return _get(data)

    on_load = get_values("on_load")
    off_load = get_values("off_load")

    current = merge({}, *[{x: on_load[x] - off_load[x]} for x in params])

    return {
        "on_load": on_load,
        "off_load": off_load,
        "current": current,
    }


@frappe.whitelist()
def get_charges_from_template(template):
    if not template:
        return None

    doc = frappe.get_doc("Shipping Order Charge Template", template)
    if not doc:
        return None

    return [
        {
            "charge_account": x.charge_account,
            "charge_amount": x.charge_amount,
            "item_description": x.item_description,
        }
        for x in doc.charges
    ]


@frappe.whitelist()
def make_payment_entry(source_name, target_doc=None):
    invoices = [
        frappe.get_cached_doc("Purchase Invoice", x.get("name"))
        for x in frappe.get_all(
            "Purchase Invoice",
            filters={
                "docstatus": 1,
                "gg_shipping_order": source_name,
                "outstanding_amount": [">", 0],
            },
            order_by="posting_date, name",
        )
    ]

    if not invoices:
        frappe.throw(frappe._("No outstanding invoices to create payment"))

    if len(list(unique([x.supplier for x in invoices]))) != 1:
        frappe.throw(
            frappe._(
                "Multiple invoices found for separate parties. "
                "Please create Payment Entry manually from Sales Invoice."
            )
        )

    return get_payment_entry_from_invoices("Purchase Invoice", invoices)


def get_shipping_order_invoice(shipping_order):
    inv_name = frappe.db.exists(
        "Purchase Invoice", {"gg_shipping_order": shipping_order, "docstatus": 1}
    )
    if not inv_name:
        return None

    inv = frappe.get_doc("Purchase Invoice", inv_name)
    result = {
        "invoice": inv.name,
        "total": inv.total,
        "total_taxes_and_charges": inv.total_taxes_and_charges,
        "grand_total": inv.grand_total,
        "rounded_total": inv.rounded_total,
        "freight": {},
        "charges": [],
    }
    freight_rates = get_freight_rates()
    for based_on in ["Packages", "Weight"]:
        freight_item = freight_rates.get(based_on) or {}
        items = [x for x in inv.items if x.item_code == freight_item["item_code"]]
        qty = sum([x.qty for x in items])
        amount = sum([x.amount for x in items])
        result["freight"][based_on] = {
            "qty": qty,
            "amount": amount,
            "rate": amount / qty,
        }

    for charge in [x for x in inv.taxes if x.add_deduct_tax == "Deduct"]:
        result["charges"].append(
            {
                "account_name": frappe.get_cached_value(
                    "Account", charge.account_head, "account_name"
                ),
                "description": charge.description,
                "tax_amount": charge.tax_amount,
            }
        )

    return result
