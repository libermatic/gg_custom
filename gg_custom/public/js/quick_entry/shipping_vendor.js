import { get_fields } from './commom_fields';

export function shipping_vendor(QuickEntryForm) {
  return class ShippingVendorQuickEntryForm extends QuickEntryForm {
    render_dialog() {
      this.mandatory = [...this.mandatory, ...this.get_variant_fields()];
      super.render_dialog();
    }
    get_variant_fields() {
      return get_fields();
    }
  };
}
