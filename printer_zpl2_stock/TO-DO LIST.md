# printer_zpl2_stock — 第二阶段改动方案与 TO-DO LIST

> 模块：`printer_zpl2_stock`
> 阶段：第二阶段（打印机选择强制化 + 产品免打印标记 + 标准批次过滤）

---

## 一、本次改动目标

1. **打印机选择强制化**：取消 `label.printer_id` 和首个 active 打印机的回退，只允许使用用户默认标签打印机；未配置或不可用时抛 `UserError` 阻止验证。
2. **产品免打印标记**：新增 `zpl_no_print` 字段，勾选后该产品的批次/序列号在自动打印时跳过。
3. **标准批次标签一并过滤**：`zpl_no_print` 同时作用于标准（非 ZPL）批次标签流程。
4. **保留错误提示区分**：未配置 vs 不可用（离线）两种消息。

---

## 二、打印机选择逻辑（改动后）

### 2.1 改动前（3 级优先级）

| 优先级 | 来源 | 条件 |
|--------|------|------|
| 1 | `env.user.default_label_printer_id` | status == 'available' |
| 2 | `label.printer_id` | 标签模板自身配置 |
| 3 | 第一个 active 打印机 | — |
| 4 | 无 | 记 warning，跳过 |

### 2.2 改动后（仅用户默认打印机）

```python
def _get_zpl_printer(self):
    self.ensure_one()
    user = self.env.user
    printer = user.default_label_printer_id
    if not printer:
        raise UserError(_(
            "用户默认打印机未配置。\n"
            "请在「用户首选项 → 默认标签打印机」中设置后再继续。"
        ))
    if printer.status != "available":
        status_label = dict(printer._fields["status"].selection).get(
            printer.status, printer.status
        )
        raise UserError(_(
            "用户默认打印机「%(printer)s」当前不可用（状态：%(status)s）。\n"
            "请检查打印机连接或更换默认打印机。",
            printer=printer.name,
            status=status_label,
        ))
    return printer
```

- 移除 `label` 参数
- 无回退，直接抛异常阻止操作
- 若该操作类型未配置任何 ZPL 标签 → 不触发打印机检查，不影响验证

### 2.3 阻止验证的场景

| 场景 | 触发方法 | 无打印机时 |
|------|----------|------------|
| 收/发货批次标签 | `stock.picking._get_autoprint_report_actions` | ❌ 阻止 `button_validate` |
| 生产工单/完成批次 | `mrp.production._get_autoprint_report_actions` | ❌ 阻止 `button_mark_done` |
| 生成批次（单个） | `mrp.production._autoprint_generated_lot` | ❌ 阻止生成 |
| 生成批次（批量） | `mrp.production._autoprint_mass_generated_lots` | ❌ 阻止生成 |
| 装箱打包标签 | `stock.move.line._post_put_in_pack_hook` | ❌ 阻止打包 |

---

## 三、产品免打印标记（zpl_no_print）

### 3.1 新增字段

`product.template`：

```python
zpl_no_print = fields.Boolean(
    string="不打印 ZPL 标签",
    help="勾选后，该产品的批次/序列号在自动打印时将跳过标签打印（ZPL 与标准流程均跳过）。",
)
```

### 3.2 生效逻辑

**ZPL 流程**：

| 位置 | 改动 |
|------|------|
| `stock.picking._resolve_lot_label` | `if product.zpl_no_print: return False, 0` |
| `mrp.production._resolve_lot_label` | `if product.zpl_no_print: return False, 0` |
| `mrp.production._autoprint_generated_lot` | `if pt.zpl_no_print: return None`（不走 `super()` 标准流程） |

**标准流程**（lot.label.layout wizard）：

| 位置 | 改动 |
|------|------|
| `stock.picking._get_autoprint_report_actions` 标准批次分支 | 传入 wizard 的 `move_line_ids` 过滤掉 `product_id.product_tmpl_id.zpl_no_print == True` 的行 |
| `mrp.production._get_autoprint_report_actions` 标准批次分支 | 同上，过滤 `move_finished_ids.move_line_ids` |
| `mrp.production._autoprint_mass_generated_lots` 标准分支 | 过滤 `lot_producing_ids` 中 `zpl_no_print` 的批次 |

### 3.3 视图

`views/product_template_views.xml` 的 "ZPL Label Configuration" 组中追加：

```xml
<field name="zpl_no_print" />
```

### 3.4 边界行为

- 单据中产品 A（需打印）+ 产品 B（勾选不打印）：仅打印 A 的标签
- 全部产品勾选不打印：不打印、不检查打印机、不报错
- 装箱标签（package 级）不受 `zpl_no_print` 影响

---

## 四、批次标签打印数量（Copies）逻辑整理

### 4.1 份数配置字段总览

| 字段 | 所属模型 | 默认值 | 约束 | 说明 |
|------|----------|--------|------|------|
| `zpl_copies_per_label` | `product.template` | 1 | 1 ~ 6（`@api.constrains`） | 产品级每份标签打印份数，优先级最高 |
| `lot_zpl2_copies` | `stock.picking.type` | 1 | 无约束 | 收/发货批号标签默认份数 |
| `package_zpl2_copies` | `stock.picking.type` | 1 | 无约束 | 包装标签默认份数 |
| `done_mrp_lot_zpl2_copies` | `stock.picking.type` | 1 | 无约束 | 生产完成批号标签默认份数 |
| `generated_mrp_lot_zpl2_copies` | `stock.picking.type` | 1 | 无约束 | 生产生成批号标签默认份数 |

> ⚠️ **当前差异**：产品级 `zpl_copies_per_label` 有 1~6 约束，但作业类型级的 4 个 `*_copies` 字段**无约束**，可填 0 或负数。`zpl_no_print` 改动时建议统一加约束（1 ~ 10），避免 0 份或负数导致 `range(0)` 不打印或 `range(-1)` 报错。

### 4.2 份数解析优先级

**批号标签（收/发货、生产完成、生产生成）**：

```
copies = 1
if product.zpl_copies_per_label > 0:
    copies = product.zpl_copies_per_label      # 优先级 1：产品级
elif picking_type.<场景>_zpl2_copies > 0:
    copies = picking_type.<场景>_zpl2_copies    # 优先级 2：作业类型级
# 否则 copies = 1
```

**包装标签**（无产品级配置，包装可能含多产品）：

```
copies = picking_type.package_zpl2_copies or 1   # 仅作业类型级
```

### 4.3 各场景对应字段

| 场景 | label 字段 | copies 字段（作业类型级） |
|------|-----------|--------------------------|
| 收/发货批号 | `lot_zpl2_label_id` | `lot_zpl2_copies` |
| 生产完成批号 | `done_mrp_lot_zpl2_label_id` | `done_mrp_lot_zpl2_copies` |
| 生产生成批号 | `generated_mrp_lot_zpl2_label_id` | `generated_mrp_lot_zpl2_copies` |
| 包装 | `package_zpl2_label_id` | `package_zpl2_copies` |

### 4.4 打印执行方式

ZPL 内容按份数循环拼接后**一次性**发送：

```python
zpl_content = b""
for _ in range(int(copies)):
    zpl_content += label._generate_zpl2_data(record)
printer.print_document(report=None, content=zpl_content, doc_format="raw")
```

> 即：N 份 = N 个 `^XA...^XZ` 块拼接为单次打印任务。

### 4.5 本次改动对份数逻辑的影响

`zpl_no_print` 不改动份数解析，仅在模板解析阶段返回 `(False, 0)` 跳过该产品。份数逻辑保持不变。

**可选优化**（本次一并处理）：为作业类型级 4 个 `*_copies` 字段增加 `@api.constrains`，约束 1 ~ 10，与产品级保持一致。

---

## 五、涉及修改的文件清单

| 文件 | 改动内容 |
|------|----------|
| `models/stock_picking.py` | `_get_zpl_printer` 简化抛错；`_resolve_lot_label` 加 `zpl_no_print` 判断；标准批次流程过滤 `zpl_no_print` 行；删除 `if not printer` 防御块 |
| `models/mrp_production.py` | `_get_zpl_printer` 简化抛错；`_resolve_lot_label` 加 `zpl_no_print` 判断；`_autoprint_generated_lot` 加 `zpl_no_print` 判断；标准批次/生成流程过滤；删除 `if not printer` 防御块 |
| `models/stock_move_line.py` | `_get_zpl_printer` 简化抛错；删除 `if not printer` 防御块 |
| `models/product_template.py` | 新增 `zpl_no_print` 字段 |
| `models/stock_picking_type.py` | 4 个 `*_copies` 字段加 `@api.constrains`（1~10） |
| `views/product_template_views.xml` | 追加 `zpl_no_print` 字段 |
| `i18n/zh_CN.po` / `.pot` | 新增翻译条目 |

---

## 六、TO-DO LIST

| # | 任务 | 涉及文件 | 状态 |
|---|------|---------|------|
| 1 | `stock_picking.py`：`_get_zpl_printer` 改为仅用户默认打印机，未配置/不可用抛 `UserError` | `models/stock_picking.py` | ✅ 已完成 |
| 2 | `mrp_production.py`：同上 | `models/mrp_production.py` | ✅ 已完成 |
| 3 | `stock_move_line.py`：同上 | `models/stock_move_line.py` | ✅ 已完成 |
| 4 | 清理所有调用处的 `if not printer: ... continue/return` 防御代码 | 3 个 models 文件 | ✅ 已完成 |
| 5 | `product_template.py`：新增 `zpl_no_print` 字段 | `models/product_template.py` | ✅ 已完成 |
| 6 | `stock_picking.py` `_resolve_lot_label`：`zpl_no_print` 返回 `(False, 0)` | `models/stock_picking.py` | ✅ 已完成 |
| 7 | `mrp_production.py` `_resolve_lot_label` + `_autoprint_generated_lot`：`zpl_no_print` 跳过 | `models/mrp_production.py` | ✅ 已完成 |
| 8 | 标准批次流程过滤 `zpl_no_print` 的产品行（stock.picking + mrp.production） | 2 个 models 文件 | ✅ 已完成 |
| 9 | `stock_picking_type.py`：4 个 `*_copies` 加 `@api.constrains`（1~10） | `models/stock_picking_type.py` | ✅ 已完成 |
| 10 | `product_template_views.xml`：追加 `zpl_no_print` 字段 | `views/product_template_views.xml` | ✅ 已完成 |
| 11 | 更新 `.pot` / `zh_CN.po` 翻译 | `i18n/` | ✅ 已完成 |
| 12 | `-u printer_zpl2_stock` 升级模块 | — | ✅ 已完成 |
| 13 | 验证：无默认打印机时阻止验证并提示 | — | ✅ 已完成 |
| 14 | 验证：默认打印机离线时阻止验证并提示 | — | ✅ 已完成 |
| 15 | 验证：`zpl_no_print` 产品批次跳过 ZPL 打印 | — | ✅ 已完成 |
| 16 | 验证：`zpl_no_print` 产品批次跳过标准流程打印 | — | ✅ 已完成 |
| 17 | 验证：`*_copies` 约束 1~10 生效 | — | ✅ 已完成 |
