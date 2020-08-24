async function set_party_name() {
  const booking_party = frappe.query_report.get_filter_value('booking_party');
  const { message: { booking_party_name } = {} } = await frappe.db.get_value(
    'Booking Party',
    booking_party,
    'booking_party_name'
  );
  frappe.query_report.set_filter_value(
    'booking_party_name',
    booking_party_name
  );
}

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
        on_change: set_party_name,
      },
      {
        fieldtype: 'Data',
        fieldname: 'booking_party_name',
        label: 'Party Name',
        read_only: 1,
      },
    ],
  };
}
