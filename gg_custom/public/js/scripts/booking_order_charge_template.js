import { set_charge_type_query } from './utils';

export function booking_order_charge_template() {
  return {
    setup: function (frm) {
      set_charge_type_query(frm);
    },
  };
}
