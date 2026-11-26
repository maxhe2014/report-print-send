========================================
Printer ZPL2 Label Print Wizard Enhanced
========================================

This module enhances the generic ZPL II label printing wizard
(``wizard.print.record.label``) provided by ``printer_zpl2``. That wizard is
attached to any model through the **Add in the 'Action' menu** button of a ZPL
label template.

The existing **Print Label** contextual action additionally supports:

* label template selection limited to the templates added to the 'Action' menu;
* three quantity modes: by product quantity, per record / serial number, or an
  exact total number of labels;
* 1 to 6 copies per unit or per record, with a live total-label preview;
* a print range by lots / serial numbers when the selected template is bound to
  ``stock.lot``;
* a default printer taken from the user's ZPL printer preference when set.

Usage
=====

1. Open a ZPL label template and click **Add in the 'Action' menu**.
2. Go to any record of the template's model and select **Print Label** in the
   *Action* menu.
3. Choose the label template, the quantity mode and, for serial-number
   templates, the lots / serial numbers to print.
4. Click **Print**; the labels are sent to the selected printer.

The label dropdown only lists templates explicitly added to the 'Action' menu
of the current model. **Remove from the 'Action' menu** detaches only that
template; the action is deleted once no template uses it anymore.

Known issues / Roadmap
======================

* Serial-number ranges are only usable when the wizard is opened on
  ``stock.lot`` records, because the label template must belong to the same
  model as the printed records.
* ``stock_move_ids`` is excluded from the lot collection to keep the wizard
  fast; current lots are collected through the stock quants instead.

Bug Tracker
===========

Bugs are tracked on the project issue tracker. In case of trouble, please
include as much information as possible (Odoo version, steps to reproduce,
error traceback and the content of the server log).

Credits
=======

Authors
-------

* metaodoo.com

Maintainers
-----------

This module is maintained by metaodoo.com and is available under the
`OPL-1 (Odoo Proprietary License v1.0)
<https://www.odoo.com/documentation/17.0/legal/licenses.html>`_ license.
