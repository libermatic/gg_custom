// Copyright (c) 2020, Libermatic and contributors
// For license information, please see license.txt

frappe.ui.form.on('Loading Operation', gg_custom.scripts.loading_operation());
frappe.ui.form.on(
  'Loading Operation Booking Order',
  gg_custom.scripts.loading_operation_booking_order()
);
