export function get_fields() {
  return [
    {
      label: __('GSTIN'),
      fieldname: '_gstin',
      fieldtype: 'Data',
    },
    {
      fieldtype: 'Section Break',
      label: __('Address Details'),
    },
    {
      label: __('Address Line 1'),
      fieldname: 'address_line1',
      fieldtype: 'Data',
    },
    {
      label: __('Address Line 2'),
      fieldname: 'address_line2',
      fieldtype: 'Data',
    },
    {
      label: __('ZIP Code'),
      fieldname: 'pincode',
      fieldtype: 'Data',
    },
    {
      fieldtype: 'Column Break',
    },
    {
      label: __('City'),
      fieldname: 'city',
      fieldtype: 'Data',
    },
    {
      label: __('State'),
      fieldname: 'state',
      fieldtype: 'Data',
    },
    {
      label: __('Country'),
      fieldname: 'country',
      fieldtype: 'Link',
      options: 'Country',
      default: frappe.defaults.get_global_default('country'),
    },
  ];
}
