import * as scripts from './scripts';
import * as quick_entry from './quick_entry';

const __version__ = '0.0.0';

frappe.provide('gg_custom');
gg_custom = { __version__, scripts };

function get_qe_classname(import_name) {
  return `${import_name
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join('')}QuickEntryForm`;
}

Object.keys(quick_entry).forEach((import_name) => {
  const extend = quick_entry[import_name];
  frappe.ui.form[get_qe_classname(import_name)] = extend(
    frappe.ui.form.QuickEntryForm
  );
});
