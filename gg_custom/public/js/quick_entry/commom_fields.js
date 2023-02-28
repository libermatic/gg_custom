export function get_fields() {
  return [
    {
      fieldtype: 'Section Break',
      label: __('Address Details'),
    },
    {
      label: __('Address Line 1'),
      fieldname: 'address_line1',
      fieldtype: 'Data',
      mandatory_depends_on: 'eval:doc._gstin||doc._phone',
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
      label: __('Phone'),
      fieldname: '_phone',
      fieldtype: 'Data',
      options: 'Phone',
    },
    {
      fieldtype: 'Column Break',
    },
    {
      label: __('City'),
      fieldname: 'city',
      fieldtype: 'Data',
      mandatory_depends_on: 'eval:doc._gstin||doc._phone',
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
    {
      label: __('GSTIN'),
      fieldname: '_gstin',
      fieldtype: 'Data',
    },
  ];
}
