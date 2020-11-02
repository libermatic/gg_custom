export function booking_summary() {
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
    ],
  };
}
