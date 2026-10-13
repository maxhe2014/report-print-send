# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import io
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def barcode(self, barcode_type, value, **kwargs):
        """Override barcode generation to use python-barcode + Pillow
        instead of reportlab (which requires rlPyCairo backend that is
        not available on this system)."""
        try:
            width = int(kwargs.get("width", 600))
            height = int(kwargs.get("height", 100))
            humanreadable = bool(int(kwargs.get("humanreadable", False)))
            quiet = bool(int(kwargs.get("quiet", True)))
            bar_border = int(kwargs.get("barBorder", 4))
            bar_level = kwargs.get("barLevel", "L")

            if barcode_type == "UPCA" and len(value) in (11, 12, 13):
                barcode_type = "EAN13"
                if len(value) in (11, 12):
                    value = "0%s" % value
            elif barcode_type == "auto":
                symbology_guess = {8: "EAN8", 13: "EAN13"}
                barcode_type = symbology_guess.get(len(value), "Code128")

            if barcode_type == "QR":
                import qrcode
                from PIL import Image

                qr = qrcode.QRCode(
                    version=None,
                    error_correction={
                        "L": qrcode.constants.ERROR_CORRECT_L,
                        "M": qrcode.constants.ERROR_CORRECT_M,
                        "Q": qrcode.constants.ERROR_CORRECT_Q,
                        "H": qrcode.constants.ERROR_CORRECT_H,
                    }.get(bar_level, qrcode.constants.ERROR_CORRECT_L),
                    box_size=max(1, width // 33),
                    border=0 if not quiet else bar_border,
                )
                qr.add_data(value)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.convert("RGB")
                img = img.resize((width, height), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

            # 1D barcodes via python-barcode
            import barcode as pybarcode
            from barcode.writer import ImageWriter
            from PIL import Image

            type_map = {
                "Code128": "code128",
                "EAN13": "ean13",
                "EAN8": "ean8",
                "UPCA": "upca",
            }
            py_type = type_map.get(barcode_type, "code128")
            BarcodeClass = pybarcode.get_barcode_class(py_type)

            writer_options = {
                "quiet_zone": quiet,
                "write_text": humanreadable,
                "module_height": height,
                "module_width": max(1, width // 100),
            }
            try:
                code = BarcodeClass(value, writer=ImageWriter())
            except Exception:
                code = pybarcode.get_barcode_class("code128")(value, writer=ImageWriter())

            buf = io.BytesIO()
            code.write(buf, options=writer_options)
            buf.seek(0)
            img = Image.open(buf)
            img = img.convert("RGB")
            if img.size != (width, height):
                img = img.resize((width, height), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="PNG")
            return out.getvalue()
        except Exception as e:
            _logger.warning("Barcode generation failed for %s: %s", barcode_type, e)
            # Return a minimal 1x1 transparent PNG as fallback
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
                b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
