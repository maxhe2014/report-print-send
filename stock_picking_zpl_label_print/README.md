# Stock Picking ZPL Label Print Module

## Overview

The Stock Picking ZPL Label Print module extends Odoo's inventory functionality to support ZPL label printing for stock pickings. This module allows users to print ZPL labels directly from stock picking records, with support for different label templates and printer configurations.

## Features

- ZPL label printing for stock pickings
- Support for multiple label templates
- User-specific printer configurations
- Label template-specific printer settings
- Integration with existing ZPL printing infrastructure

## Technical Implementation

### Key Components

1. **Models**:
   - `res.users` extension with ZPL printer configuration fields
   - `printing.label.zpl2.user.action` model for label-specific printer settings
   - `stock.picking` extension with print label wizard action
   - `print.picking.zpl.label.wizard` for label printing configuration

2. **Views**:
   - User preferences form with ZPL printer settings
   - Label template printer configuration interface
   - Picking form with print label button
   - Label printing wizard

3. **Dependencies**:
   - `stock` - Odoo's inventory management module
   - `printer_zpl2` - ZPL printing infrastructure
   - `mrp_zpl_label_print` - MRP ZPL label printing module (provides base ZPL printer settings)

### Printer Configuration Priority

The module implements a priority-based printer selection system:

1. **Label template-specific printer** - If a user has configured a specific printer for a label template, this takes highest priority
2. **User default ZPL printer** - If no template-specific printer is configured, the user's default ZPL printer is used

## Usage Instructions

### Setting Up Printer Configuration

1. **User Default ZPL Printer**:
   - Go to Settings > Users & Companies > Users
   - Edit your user record
   - Under Preferences > ZPL Label Printing, select your default ZPL printer

2. **Label Template-Specific Printers**:
   - Go to Settings > Printing > ZPL Label Configurations
   - Click "Create" to add a new configuration
   - Enter a name for the configuration
   - Select the user, label template, and printer
   - Click "Save" to save the configuration
   - To copy an existing configuration, open the configuration and click "Copy" button
   - To delete a configuration, select it in the list view and click the "Delete" button

### Printing Labels

1. **From Stock Picking**:
   - Open a stock picking record
   - Click the "Print ZPL Label" button
   - Select the label template (defaults to your configured default)
   - Adjust the number of copies if needed
   - Click "Print" to print the label

2. **From Lots/Serial Numbers**:
   - Select one or more lot/serial number records
   - Click the "Print ZPL Label" button
   - Select a label template designed for lots/serial numbers
   - Adjust the number of copies if needed
   - Click "Print" to print the labels

## Troubleshooting

### Common Issues

1. **Error: UndefinedColumn: column res_users.zpl_picking_label_template_id does not exist**
   - **Cause**: The module was not properly upgraded after adding the new field
   - **Solution**: Upgrade the module through Odoo's Apps interface or by running the appropriate upgrade command

2. **No printer available in the wizard**
   - **Cause**: No default printer configured for the user or label template
   - **Solution**: Set up a default ZPL printer in user preferences

3. **Label printing fails**
   - **Cause**: Printer not connected or ZPL template error
   - **Solution**: Check printer connection and ensure the label template is valid

## Version History

- **17.0.1.0.4** - Fixed copy functionality to avoid unique constraint error, added delete button to tree view
- **17.0.1.0.3** - Added copy functionality for ZPL label configurations, enabled delete functionality in tree view
- **17.0.1.0.2** - Moved ZPL label printer configuration to Settings/Printing menu, removed Paper Source field
- **17.0.1.0.1** - Fixed missing field issue and added label template-specific printer configuration
- **17.0.1.0.0** - Initial release

## Support

For support with this module, please contact your Odoo administrator or the module developer.
