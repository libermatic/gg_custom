import * as scripts from './scripts';
import * as reports from './reports';
import * as cscripts from './cscripts';
import * as quick_entry from './quick_entry';

const __version__ = '13.0.4';

frappe.provide('gg_custom');
gg_custom = { __version__, scripts, reports };

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

function get_doctype(import_name) {
  return import_name
    .split('_')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ');
}

Object.keys(cscripts).forEach((import_name) => {
  const get_handler = cscripts[import_name];
  frappe.ui.form.on(get_doctype(import_name), get_handler());
});
