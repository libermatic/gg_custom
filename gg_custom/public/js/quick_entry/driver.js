import { get_fields } from './common_fields';

export function driver(QuickEntryForm) {
  return class DriverQuickEntryForm extends QuickEntryForm {
    render_dialog() {
      this.mandatory = [...this.mandatory, ...this.get_variant_fields()];
      super.render_dialog();
    }
    get_variant_fields() {
      return get_fields();
    }
  };
}
