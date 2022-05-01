export function driver() {
  return {
    refresh: async function (frm) {
      frappe.dynamic_link = {
        doc: frm.doc,
        fieldname: 'name',
        doctype: 'Driver',
      };
      frm.toggle_display('address_sec', !frm.doc.__islocal);
      if (frm.doc.__islocal) {
        frappe.contacts.clear_address_and_contact(frm);
      } else {
        const addr_list = await frappe.db.get_list('Address', {
          filters: { name: ['like', `${frm.doc.name}%`] },
          fields: ['*'],
        });
        frm.doc.__onload = {
          addr_list: addr_list.map((x) => ({
            ...x,
            display: `${x.address_line1}<br />${x.city}`,
          })),
          contact_list: [],
        };
        frappe.contacts.render_address_and_contact(frm);
      }
    },
  };
}
