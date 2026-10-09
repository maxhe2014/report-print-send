# printer_zpl2_stock — 实现方案与 TO-DO LIST

> 模块：`printer_zpl2_stock`（桥接 `printer_zpl2` 与 `stock`）
> 参考：`/run/media/max/DATA1/projects/odoo-dev/17.0/addons/report-print-send/mrp_zpl_label_print`

---

## 一、需求概述

在 Odoo 19 库存模块中，让用户能为**批号/序号标签**和**包装标签**选择自定义 ZPL II 标签模板并自动打印。支持三级配置优先级：产品级 > 作业类型级 > 系统默认，打印机取自用户首选项。

---

## 二、配置界面设计

### 2.1 用户首选项 — 默认标签打印机（复用现有字段，不新增）

**位置**：设置 → 用户与公司 → 用户 → 偏好（Preferences）页签 → Printing 组

**复用字段**：`default_label_printer_id`（由 `base_report_to_label_printer` 模块提供，string="Default Label Printer"）

> 本模块**不新增**任何用户字段。直接使用用户首选项中已有的 "Default Label Printer"（`default_label_printer_id`）作为 ZPL 标签打印的默认打印机。该字段已由 `base_report_to_label_printer` 加入 `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS`，用户可自行配置。
>
> **依赖说明**：`printer_zpl2_stock` 的 `__manifest__.py` 需添加 `base_report_to_label_printer` 到 `depends`（该模块依赖 `base_report_to_printer`，而 `printer_zpl2` 已依赖 `base_report_to_printer_cups` → `base_report_to_printer`，不会产生循环依赖）。

### 2.2 产品 — ZPL 标签模板与份数

**位置**：产品 → 常规信息（General Information）页签

**字段**：

| 字段 | 类型 | domain / 约束 | 说明 |
|------|------|---------------|------|
| `zpl_label_template_id` | Many2one → `printing.label.zpl2` | `[('model_id.model', 'in', ['stock.lot', 'stock.package'])]` | 产品专属 ZPL 标签模板，优先级最高 |
| `zpl_copies_per_label` | Integer | 1 ~ 6，default=1 | 每个标签打印份数 |

**视图锚点**：`product.product_template_form_view` 的 `<page name="general_information">` 内，在 `group_standard_price` 之后追加 "ZPL Label Configuration" 组（仅 `type == 'product'` 时可见）。

### 2.3 作业类型 — Hardware 页签默认配置

**位置**：库存 → 作业类型 → Hardware 页签

**字段**（追加到现有 Lot/SN Labels 和 Package Label 行）：

| 字段 | 类型 | domain | 说明 |
|------|------|--------|------|
| `lot_zpl2_label_id` | Many2one → `printing.label.zpl2` | `[('model_id.model', '=', 'stock.lot')]` | 批号/序号默认标签模板（产品级未配置时使用） |
| `lot_zpl2_copies` | Integer | default=1 | 批号标签默认份数 |
| `package_zpl2_label_id` | Many2one → `printing.label.zpl2` | `[('model_id.model', '=', 'stock.package')]` | 包装默认标签模板 |
| `package_zpl2_copies` | Integer | default=1 | 包装标签默认份数 |

**UI 布局**（在 `lot_label_format` 和 `package_label_to_print` 字段之后追加）：

```
[✓] Lot/SN Labels   Print label as: [4x12 Lots ▾]   Custom ZPL Label: [选择 ▾]   Copies: [1]
[✓] Package Label   Print label as: [PDF ▾]          Custom ZPL Label: [选择 ▾]   Copies: [1]
```

显隐：与 `auto_print_lot_labels` / `auto_print_package_label` 联动。

---

## 三、优先级逻辑

### 3.1 标签模板选择

| 场景 | 优先级 | 来源 |
|------|--------|------|
| 批号标签 | 1（最高） | `lot.product_id.product_tmpl_id.zpl_label_template_id` |
|          | 2 | `picking_type.lot_zpl2_label_id` |
|          | 3（最低） | 走标准 QWeb 流程（不使用自定义 ZPL） |
| 包装标签 | 1 | `picking_type.package_zpl2_label_id`（包装可能含多产品，取作业类型默认） |
|          | 2 | 走标准 QWeb 流程 |

> 批号标签按 lot 逐个解析：每个 lot 先看其产品是否配置了专属模板，没有再回退到作业类型默认。

### 3.2 打印机选择

| 优先级 | 来源 | 条件 |
|--------|------|------|
| 1 | `env.user.default_label_printer_id` | 在线（status='online'） |
| 2 | `label.printer_id` | 标签模板自身配置的打印机 |
| 3 | 第一个 active 打印机 | — |
| 4 | 无 | 记 warning 日志，跳过打印 |

### 3.3 打印份数

| 场景 | 优先级 | 来源 |
|------|--------|------|
| 批号标签 | 1 | `lot.product_id.product_tmpl_id.zpl_copies_per_label`（>0 时） |
|          | 2 | `picking_type.lot_zpl2_copies` |
|          | 3 | 1 |
| 包装标签 | 1 | `picking_type.package_zpl2_copies` |
|          | 2 | 1 |

---

## 四、打印流程实现原理

### 4.1 批号标签（拣货单验证时自动打印）

**入口**：重写 `stock.picking._get_autoprint_report_actions()`

**流程**：
1. 筛选 `auto_print_lot_labels=True` 且有 `lot_id` 的拣货单
2. 按 lot 分组，对每个 lot 解析模板和份数：
   - 模板 = 产品级模板 or 作业类型默认模板
   - 若两者都无 → 归入"标准流程"（走 `lot.label.layout` wizard）
3. 对有自定义模板的 lot：
   - 解析打印机（按 3.2 优先级）
   - 批量生成 ZPL 内容（`for _ in range(copies): zpl += label._generate_zpl2_data(lot)`）
   - 一次 `printer.print_document(report=None, content=zpl, doc_format='raw')` 发送
4. 标准流程的拣货单走原有 `lot.label.layout` wizard，返回 report action

**容错**：每个 lot 的打印用 `try/except` 包裹，失败记日志不阻断验证。

### 4.2 包装标签（"Put in Pack" 时自动打印）

**入口**：重写 `stock.move.line._post_put_in_pack_hook(package)`

**流程**：
1. 若 `picking_type.package_zpl2_label_id` 已设置：
   - 解析打印机
   - 生成 ZPL 内容（循环 `package_zpl2_copies` 次）
   - 发送打印
   - 返回 `package`（不走标准 report action）
2. 否则 → `super()` 走原有 PDF / 标准 ZPL 流程

---

## 五、模块文件结构

```
printer_zpl2_stock/
├── __manifest__.py                    # depends: printer_zpl2, stock, base_report_to_label_printer
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── product_template.py            # zpl_label_template_id, zpl_copies_per_label
│   ├── stock_picking_type.py          # lot/package_zpl2_label_id, *_copies
│   ├── stock_picking.py               # 重写 _get_autoprint_report_actions
│   └── stock_move_line.py             # 重写 _post_put_in_pack_hook
└── views/
    ├── product_template_views.xml     # 产品 ZPL 配置
    └── stock_picking_type_views.xml   # 作业类型 Hardware 页签
```

---

## 六、TO-DO LIST

| # | 任务 | 涉及文件 | 状态 |
|---|------|---------|------|
| 1 | 创建 `models/product_template.py`：`zpl_label_template_id` + `zpl_copies_per_label` + 约束 | `models/product_template.py` | ✅ 已完成 |
| 2 | 创建 `models/stock_picking_type.py`：4 个字段（2 模板 + 2 份数） | `models/stock_picking_type.py` | ✅ 已完成 |
| 3 | 创建 `models/stock_picking.py`：重写 `_get_autoprint_report_actions`（批号标签三级优先级 + 批量打印） | `models/stock_picking.py` | ✅ 已完成 |
| 4 | 创建 `models/stock_move_line.py`：重写 `_post_put_in_pack_hook`（包装标签） | `models/stock_move_line.py` | ✅ 已完成 |
| 5 | 创建 `views/product_template_views.xml`：产品常规信息追加 ZPL 配置组 | `views/product_template_views.xml` | ✅ 已完成 |
| 6 | 创建 `views/stock_picking_type_views.xml`：Hardware 页签追加字段 | `views/stock_picking_type_views.xml` | ✅ 已完成 |
| 7 | 更新 `__manifest__.py`：depends 加 `base_report_to_label_printer`，data 列表加视图；`models/__init__.py` 加 product_template 导入 | `__manifest__.py`, `models/__init__.py` | ✅ 已完成 |
| 8 | 安装模块 `-i printer_zpl2_stock`，验证无报错 | — | ✅ 已完成 |
| 9 | 验证 UI：产品 / 作业类型 字段正确显示 | — | ✅ 已完成（shell 验证字段注册） |
| 10 | 验证批号标签打印：产品级模板优先 > 作业类型默认 > 标准流程 | — | ✅ 已完成（shell 验证） |
| 11 | 验证包装标签打印：自定义模板 vs 标准流程切换 | — | ✅ 已完成（shell 验证） |
| 12 | 验证打印机优先级：用户 Default Label Printer (`default_label_printer_id`) > 标签打印机 > 首个活跃打印机 | — | ✅ 已完成（shell 验证） |

---

## 七、关键避坑（参考 lessons_learned.md）

1. **xpath 锚点用 `@name` 不用 `@string`**：视图继承一律 `//field[@name='xxx']` / `//group[@name='xxx']`
2. **Owl QWeb 用 JS 运算符**：`!` / `&&` / `||`，XML 中 `&&` 转义为 `&amp;&amp;`；但 field domain 属 Python 域语法，可用 `not`
3. **`clean_action` 导入**：`from odoo.addons.web.controllers.utils import clean_action`
4. **XML 修改必须 `-u` 升级**：`dev_mode=reload` 只热更 Python
5. **Odoo 19 包装模型名**：`stock.package`（非旧版 `stock.quant.package`）
6. **`print_label` 内部校验模型**：`record._name == label.model_id.model`，domain 必须保证一致
7. **复用现有标签打印机字段**：不新增用户打印机字段，直接用 `base_report_to_label_printer` 的 `default_label_printer_id`（用户首选项 "Default Label Printer"），其已加入 `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS`；需在 `__manifest__.py` 的 `depends` 中添加 `base_report_to_label_printer`
8. **批量打印性能**：多个 label 的 ZPL 内容拼接后一次 `print_document` 发送，而非逐个调用
