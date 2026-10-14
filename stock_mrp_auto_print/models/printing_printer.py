# Copyright 2026
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

# Odoo paperformat.format -> CUPS media keyword
PAPERFORMAT_TO_CUPS_MEDIA = {
    "A4": "iso_a4",
    "A3": "iso_a3",
    "A5": "iso_a5",
    "Letter": "na_letter_8.5x11in",
    "Legal": "na_legal_8.5x14in",
}

# CUPS InputSlot 选项值 -> IPP media-source 关键字
# 柯美等 IPP 打印机不识别 InputSlot，导致进纸纸盒设置被忽略、
# 机器按自身默认（手送优先）选纸；转换为 media-source 后机器才正确识别。
INPUT_SLOT_TO_MEDIA_SOURCE = {
    "Auto": "auto",
    "ByPassTray": "by-pass-tray",
    "Tray1": "tray-1",
    "Tray2": "tray-2",
    "Tray3": "tray-3",
    "Tray4": "tray-4",
}


class PrintingPrinter(models.Model):
    _inherit = "printing.printer"

    default_media_type = fields.Selection(
        selection=[
            ("none", "不发送（由打印机决定）"),
            ("stationery", "普通纸"),
            ("stationery-lightweight", "薄纸"),
            ("stationery-heavyweight", "厚纸"),
            ("stationery-heavyweight3", "厚纸3"),
        ],
        string="默认纸张类型",
        default="stationery",
        help="打印任务中携带的纸张类型。打印机纸盒的纸张类型需与此一致，"
        "否则机器会提示纸张不匹配。选择“不发送”时任务不携带类型，"
        "打印机将使用机身默认类型。",
    )

    def print_options(self, report=None, **print_opts):
        """附加纸张尺寸与类型，避免打印机用机身默认值（如 Letter+厚纸）兜底。"""
        options = super().print_options(report=report, **print_opts)
        paperformat = report.paperformat_id if report else False
        media = PAPERFORMAT_TO_CUPS_MEDIA.get(paperformat.format) if paperformat else False
        if media:
            options.setdefault("media", media)
        if self.default_media_type and self.default_media_type != "none":
            options.setdefault("media-type", self.default_media_type)
        input_slot = options.pop("InputSlot", None)
        media_source = INPUT_SLOT_TO_MEDIA_SOURCE.get(input_slot)
        if media_source:
            options.setdefault("media-source", media_source)
        return options
