export function shipping_vendor() {
  return {
    setup: function (frm) {
      frm.set_query('primary_address', function (doc) {
        return {
          filters: {
            link_doctype: 'Shipping Vendor',
            link_name: doc.name,
          },
        };
      });
    },
    refresh: function (frm) {
      frappe.dynamic_link = {
        doc: frm.doc,
        fieldname: 'name',
        doctype: 'Vehicle Vendor',
      };
      frm.toggle_display('address_sec', !frm.doc.__islocal);
      if (frm.doc.__islocal) {
        frappe.contacts.clear_address_and_contact(frm);
      } else {
        frappe.contacts.render_address_and_contact(frm);
      }
      if (!frm.doc.__islocal && frm.doc.__onload) {
        erpnext.utils.set_party_dashboard_indicators(frm);
      }

      if (!frm.doc.__islocal && frm.doc.supplier) {
        frm.add_custom_button('Create Payment', () => create_payment(frm));
      }
    },
    primary_address: function (frm) {
      if (!frm.doc.primary_address) {
        frm.set_value('phone', null);
      }
    },
  };
}

export function shipping_vendor_listview_settings() {
  return {
    filters: [['disabled', '=', 0]],
  };
}

function create_payment(frm) {
  frappe.model.open_mapped_doc({
    method: 'gg_custom.api.shipping_vendor.make_payment_entry',
    frm,
  });
}
