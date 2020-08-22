// Copyright (c) 2020, Libermatic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Booking Order', gg_custom.scripts.booking_order());
frappe.ui.form.on(
  'Booking Order Freight Detail',
  gg_custom.scripts.booking_order_freight_detail()
);
frappe.ui.form.on(
  'Booking Order Charge',
  gg_custom.scripts.booking_order_charge()
);
