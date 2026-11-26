# Copyright 2026 metaodoo.com
# License OPL-1 (https://www.odoo.com/documentation/17.0/legal/licenses.html).

"""Runtime extensions for the ZPL II generator of ``printer_zpl2``.

The base addon is left untouched: these hooks add the custom font, Data
Matrix and text truncation features used by our labels without copying
the AGPL code of ``printer_zpl2`` into this module.
"""

from odoo.addons.printer_zpl2.models import zpl2

FONT_CUSTOM = "@"
BARCODE_QR_CODE_CUSTOM = "qr_code_custom"
BARCODE_DATA_MATRIX = "datamatrix"

_ORIG_FONT_FORMAT = zpl2.Zpl2._font_format
_ORIG_BARCODE_FORMAT = zpl2.Zpl2._barcode_format
_ORIG_BARCODE_DATA = zpl2.Zpl2.barcode_data
_ORIG_FONT_DATA = zpl2.Zpl2.font_data


def _truncate_block_text(data, field_format):
    """Truncate text so that it fits the configured block dimensions."""
    if not isinstance(data, str) or not data:
        return data

    block_width = field_format.get(zpl2.ARG_BLOCK_WIDTH, 0)
    block_lines = field_format.get(zpl2.ARG_BLOCK_LINES, 1)
    block_spaces = field_format.get(zpl2.ARG_BLOCK_SPACES, 0)
    font_height = field_format.get(zpl2.ARG_HEIGHT, 12)

    if block_width <= 0 or block_lines <= 0:
        return data

    chinese_chars = sum(1 for char in data if ord(char) > 127)
    english_chars = len(data) - chinese_chars

    base_width_factor = font_height / 12.0
    chinese_char_width = 16 * base_width_factor
    english_char_width = 8 * base_width_factor

    total_width = (
        chinese_chars * chinese_char_width + english_chars * english_char_width
    )
    avg_char_width = total_width / len(data) if data else 10 * base_width_factor

    space_factor = 1.0 - (block_spaces * 0.05)
    effective_block_width = block_width * max(0.7, space_factor)

    chars_per_line = max(1, int(effective_block_width / avg_char_width * 0.9))
    max_chars = chars_per_line * block_lines

    if len(data) <= max_chars:
        return data

    keep_chars = max(1, max_chars - 1)
    return data[:keep_chars] + "..."


def _font_format(self, font_format):
    font = font_format.get(zpl2.ARG_FONT) or ""
    if isinstance(font, str) and font.startswith(FONT_CUSTOM):
        name = font[len(FONT_CUSTOM) :]
        orientation = font_format.get(
            zpl2.ARG_ORIENTATION, zpl2.ORIENTATION_NORMAL
        )
        height = self._enforce(font_format.get(zpl2.ARG_HEIGHT, 10), minimum=10)
        width = self._enforce(font_format.get(zpl2.ARG_WIDTH, 10), minimum=10)
        return f"^A@{orientation},{height},{width},{name}"
    return _ORIG_FONT_FORMAT(self, font_format)


def _barcode_format(self, barcode_type, barcode_format):
    if barcode_type == BARCODE_QR_CODE_CUSTOM:
        return _ORIG_BARCODE_FORMAT(
            self, zpl2.BARCODE_QR_CODE, barcode_format
        )
    if barcode_type == BARCODE_DATA_MATRIX:
        orientation = barcode_format.get(
            zpl2.ARG_ORIENTATION, zpl2.ORIENTATION_NORMAL
        )
        height = barcode_format.get(zpl2.ARG_HEIGHT) or 5
        quality = barcode_format.get(zpl2.ARG_SECURITY_LEVEL) or 200
        columns = barcode_format.get(zpl2.ARG_COLUMNS_COUNT) or 36
        rows = barcode_format.get(zpl2.ARG_ROWS_COUNT) or 36
        return f"^BX{orientation},{height},{quality},{columns},{rows},1,_,1"
    return _ORIG_BARCODE_FORMAT(self, barcode_type, barcode_format)


def barcode_data(self, right, down, barcode_type, barcode_format, data):
    if barcode_type == BARCODE_QR_CODE_CUSTOM:
        error_correction = (
            barcode_format.get(zpl2.ARG_ERROR_CORRECTION)
            or zpl2.ERROR_CORRECTION_STANDARD
        )
        data = f"{error_correction}A,{data}"
        barcode_type = zpl2.BARCODE_QR_CODE
    return _ORIG_BARCODE_DATA(
        self, right, down, barcode_type, barcode_format, data
    )


def font_data(self, right, down, field_format, data):
    if field_format.get(zpl2.ARG_IN_BLOCK):
        data = _truncate_block_text(data, field_format)
    return _ORIG_FONT_DATA(self, right, down, field_format, data)


zpl2.Zpl2._font_format = _font_format
zpl2.Zpl2._barcode_format = _barcode_format
zpl2.Zpl2.barcode_data = barcode_data
zpl2.Zpl2.font_data = font_data
