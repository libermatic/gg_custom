export function sales_invoice() {
  return {
    onload: async function (frm) {
      const [page, doctype] = frappe.get_prev_route();
      const { __islocal, taxes_and_charges } = frm.doc;
      if (
        __islocal &&
        page === 'Form' &&
        doctype === 'Booking Order' &&
        taxes_and_charges
      ) {
        await frm.trigger('taxes_and_charges');
      }
    },
  };
}
