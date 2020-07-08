function set_address(party_type) {
  const address_field = `${party_type}_address`;
  return async function (frm) {
    if (frm.doc[party_type]) {
      const { message: { primary_address } = {} } = await frappe.db.get_value(
        'Booking Party',
        frm.doc[party_type],
        'primary_address'
      );
      frm.set_value(address_field, primary_address);
    } else {
      frm.set_value(address_field, null);
    }
  };
}

function set_address_dispay(party_type) {
  const address_field = `${party_type}_address`;
  const display_field = `${party_type}_address_display`;
  return async function (frm) {
    erpnext.utils.get_address_display(frm, address_field, display_field);
  };
}

function set_total_amount(frm) {
  const total_amount = frm.doc.charges
    .map((x) => x.charge_amount)
    .reduce((a, x) => a + x, 0);
  frm.set_value({ total_amount });
}

export function booking_order_charge() {
  return {
    charge_amount: set_total_amount,
    charges_remove: set_total_amount,
  };
}

export function booking_order() {
  return {
    consignor: set_address('consignor'),
    consignee: set_address('consignee'),
    consignor_address: set_address_dispay('consignor'),
    consignee_address: set_address_dispay('consignee'),
    booking_order_charge_template: async function (frm) {
      cur_frm.clear_table('charges');
      const { booking_order_charge_template } = frm.doc;
      if (booking_order_charge_template) {
        const charges = await frappe.db.get_list('Booking Order Charge', {
          fields: ['charge_type'],
          parent: 'Booking Order Charge Template',
          filters: {
            parenttype: 'Booking Order Charge Template',
            parent: booking_order_charge_template,
          },
        });
        charges.forEach((row) => {
          frm.add_child('charges', row);
        });
      }
      cur_frm.refresh_field('charges');
      set_total_amount(frm);
    },
  };
}
