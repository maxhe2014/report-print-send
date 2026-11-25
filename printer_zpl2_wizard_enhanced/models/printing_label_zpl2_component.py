# Copyright (C) 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

from odoo import fields, models
from odoo.addons.printer_zpl2.models import zpl2

from .zpl2_patch import (
    BARCODE_DATA_MATRIX,
    BARCODE_QR_CODE_CUSTOM,
    FONT_CUSTOM,
)


class PrintingLabelZpl2Component(models.Model):
    _inherit = "printing.label.zpl2.component"

    component_type = fields.Selection(
        selection_add=[
            (BARCODE_QR_CODE_CUSTOM, "QR Code (Custom)"),
            (BARCODE_DATA_MATRIX, "Data Matrix"),
        ],
        ondelete={
            BARCODE_QR_CODE_CUSTOM: "cascade",
            BARCODE_DATA_MATRIX: "cascade",
        },
    )
    font = fields.Selection(
        selection_add=[(FONT_CUSTOM, "Custom Font")],
        ondelete={FONT_CUSTOM: "cascade"},
    )
    custom_font_name = fields.Char(
        string="Custom Font Name",
        help="Name of the custom font file (e.g., 11519722.TTF). "
        "This font must be already uploaded to the printer.",
    )
    quality = fields.Integer(
        string="Quality",
        default=200,
        help="Data Matrix quality level (0-400). Higher values improve "
        "readability but increase size.",
    )
    columns = fields.Integer(
        string="Columns",
        default=36,
        help="Force number of columns (0=automatic).",
    )
    rows = fields.Integer(
        string="Rows",
        default=36,
        help="Force number of rows (0=automatic).",
    )
    format_type = fields.Selection(
        selection=[
            ("0", "None"),
            ("1", "Field"),
            ("2", "Structured"),
        ],
        string="Format Type",
        default="1",
        help="Data Matrix format type.",
    )
    escape_sequence = fields.Boolean(
        string="Escape Sequence",
        default=True,
        help="Enable escape sequences in Data Matrix data.",
    )
    additional_info = fields.Boolean(
        string="Additional Info",
        default=True,
        help="Add additional information to Data Matrix.",
    )

    def __getitem__(self, key):
        """Expose computed values through the keys read by the generator.

        ``printer_zpl2`` builds the generator arguments with
        ``component[field_name]``, so this is the only way to forward the
        custom font file name and the Data Matrix options without patching
        that AGPL code.
        """
        value = super().__getitem__(key)
        if len(self) != 1:
            return value
        if key == zpl2.ARG_FONT and value == FONT_CUSTOM and self.custom_font_name:
            return f"{FONT_CUSTOM}{self.custom_font_name}"
        if self.component_type == BARCODE_DATA_MATRIX:
            if key == zpl2.ARG_SECURITY_LEVEL:
                return self.quality or value
            if key == zpl2.ARG_COLUMNS_COUNT:
                return self.columns or value
            if key == zpl2.ARG_ROWS_COUNT:
                return self.rows or value
        return value
