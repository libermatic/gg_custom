export function booking_accounting_ledger() {
  return {
    filters: [
      {
        fieldtype: 'Date',
        fieldname: 'from_date',
        label: 'From',
        default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
        reqd: 1,
      },
      {
        fieldtype: 'Date',
        fieldname: 'to_date',
        label: 'To',
        default: frappe.datetime.get_today(),
        reqd: 1,
      },
      {
        fieldtype: 'Link',
        options: 'Booking Party',
        fieldname: 'booking_party',
        label: 'Booking Party',
        reqd: 1,
      },
    ],
  };
}
