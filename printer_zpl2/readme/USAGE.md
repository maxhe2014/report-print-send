To print a label, you need to call use the label printing method from
anywhere (other modules, server actions, etc.).

Example : Print the label of a product :

    self.env['printing.label.zpl2'].browse(label_id).print_label(
        self.env['printing.printer'].browse(printer_id),
        self.env['product.product'].browse(product_id))

You can also use the generic label printing wizard, if added on some
models.

## Print Darkness Control

The module supports controlling print darkness using the ZPL ^MD command.
You can set the darkness value in the label configuration, ranging from
-30 (lightest) to 30 (darkest), with 0 being the default value.

[![Try me on Runbot](https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas)](https://runbot.odoo-community.org/runbot/144/12.0)