export function booking_party() {
  return {
    setup: function (frm) {
      frm.set_query('primary_address', function (doc) {
        return {
          filters: {
            link_doctype: 'Booking Party',
            link_name: doc.name,
          },
        };
      });
    },
    refresh: function (frm) {
      frappe.dynamic_link = {
        doc: frm.doc,
        fieldname: 'name',
        doctype: 'Booking Party',
      };
      frm.toggle_display('address_sec', !frm.doc.__islocal);
      if (frm.doc.__islocal) {
        frappe.contacts.clear_address_and_contact(frm);
      } else {
        frappe.contacts.render_address_and_contact(frm);
      }
      if (!frm.doc.__islocal && !frm.doc.customer) {
        frm.add_custom_button('Create Customer', async function () {
          try {
            await frm.call('create_customer');
            frm.reload_doc();
          } finally {
            frm.refresh();
          }
        });
      }
      if (!frm.doc.__islocal && frm.doc.__onload) {
        erpnext.utils.set_party_dashboard_indicators(frm);
      }
    },
    primary_address: function (frm) {
      if (!frm.doc.primary_address) {
        frm.set_value('phone', null);
      }
    },
  };
}
