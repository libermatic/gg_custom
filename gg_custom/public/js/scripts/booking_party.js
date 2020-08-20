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
        render_booking_order_links(frm);
      }
    },
    primary_address: function (frm) {
      if (!frm.doc.primary_address) {
        frm.set_value('phone', null);
      }
    },
  };
}

export function booking_party_listview_settings() {
  return {
    filters: [['disabled', '=', 0]],
  };
}

function render_booking_order_links(frm) {
  frm.dashboard.transactions_area.empty();
  const fields = ['consignor', 'consignee'];
  frm.dashboard.transactions_area.append(
    frappe.render_template('form_links', {
      transactions: [
        {
          label: 'Shipping',
          items: fields.map((field) => `Booking Order as ${field}`),
        },
      ],
      internal_links: {},
    })
  );

  function route_handler(field) {
    return function () {
      frappe.route_options = { [field]: frm.doc.name };
      frappe.set_route('List', 'Booking Order', 'List');
    };
  }

  fields.forEach(async function (field) {
    const $link = frm.dashboard.transactions_area.find(
      `.document-link[data-doctype='Booking Order as ${field}']`
    );
    $link.find('.badge-link').on('click', route_handler(field));
    const [{ count } = {}] = await frappe.db.get_list('Booking Order', {
      filters: { [field]: frm.doc.name },
      fields: ['count(name) as count'],
    });
    if (count) {
      $link.find('.count').text(count);
    }
  });

  frm.dashboard.links_area.removeClass('hidden');
  frm.dashboard.show();
}
