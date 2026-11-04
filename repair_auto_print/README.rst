=================
Repair Auto Print
=================

Automatically print repair orders, product labels, and lot/serial number
labels when repairs are completed. Native PDF and ZPL reports are preserved,
and custom ZPL II templates can be sent directly to a label printer.

Configuration
=============

Repair operation type
---------------------

Open a repair operation type and use its **Hardware** tab to enable each
automatic print option independently. Product and lot/SN labels can use the
native PDF/ZPL format or a default custom ZPL II template. Default copy counts
accept values from 1 to 10.

Product template
----------------

On a stockable product's **General Information** page, configure repair-specific
product and lot/SN ZPL II templates. These settings are shared by all variants.
A product template takes priority over the operation type default. Copy counts
from 1 to 10 override the operation type; 0 inherits its setting.

Product labels accept templates bound to ``repair.order``, ``product.product``,
or ``product.template``. Lot/SN labels must use ``stock.lot`` templates.

Printing behavior
=================

* A label is printed only when its corresponding automatic print switch is on.
* With no custom template, the existing native PDF/ZPL report is used.
* A custom template is printed directly as raw ZPL II and its native report is
  not emitted, preventing duplicate labels.
* Product labels use one label per repair multiplied by the effective copies.
* Lot/SN labels use the ceiling of the repair quantity multiplied by the
  effective copies.
* Repairs without a lot/SN skip lot/SN labels.

Printer resolution uses this order:

1. The current user's active printer for the selected ZPL II label.
2. The label template's default printer.
3. The current user's default label printer.

Missing or unavailable printers, unsupported template models, and print
failures raise an explicit error. The module does not silently fall back to a
different printer or native report.

Credits
=======

Authors
-------

* 宁波企智信息科技有限公司

Maintainers
-----------

This module is maintained by 宁波企智信息科技有限公司 and the Odoo Community
Association (OCA).
