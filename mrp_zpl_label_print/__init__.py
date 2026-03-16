from odoo import api, SUPERUSER_ID
from odoo.exceptions import MissingError
import logging

_logger = logging.getLogger(__name__)

# 检查依赖模块
@api.model
def _check_dependencies(cr, registry):
    """检查模块依赖"""
    try:
        # 检查 printer_zpl2 模块是否安装
        with registry.cursor() as cr:
            cr.execute("""
                SELECT id FROM ir_module_module 
                WHERE name = 'printer_zpl2' AND state = 'installed'
            """)
            result = cr.fetchone()
            if not result:
                _logger.error("MRP ZPL Label Print: printer_zpl2 module is not installed")
                raise MissingError(
                    "MRP ZPL Label Print 模块依赖于 printer_zpl2 模块，请先安装该模块"
                )
    except Exception as e:
        _logger.error(f"MRP ZPL Label Print: Dependency check failed: {e}")
        raise

from . import models
from . import wizards