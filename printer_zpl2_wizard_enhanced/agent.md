# ZPL 通用打印向导增强模块（printer_zpl2_wizard_enhanced）

## 1. 模块定位

本模块**增强 `printer_zpl2` 的通用打印向导** `wizard.print.record.label`，不新增任何按钮，也不绑定任何业务模型。

`printer_zpl2` 的 ZPL 模板表单上有 **Add in the 'Action' menu** 按钮，可为任意模型（如 `repair.order`、`mrp.production`、`stock.picking`）创建一个「打印标签」上下文动作，打开的就是这个通用向导。本模块通过继承它，让同一个「打印标签」菜单项支持：

- 标签模板选择（`printer_zpl2` 原有能力）
- **三种数量计算方式**：按产品数量 / 按记录或序列号 / 精确指定总张数
- 份数选择（每单位/记录 1–6）与**总张数实时预览**
- **打印范围选择**（按批次/序列号，任意关联 `stock.lot` 的模型）
- 打印机默认取个人资料的 `zpl_printer_id`（若安装了提供该字段的模块，否则回退通用向导的默认选择）

用户无需更换入口，也不会看到两个功能重叠的按钮。

### 背景：原版通用向导缺什么

`printer_zpl2/wizard/print_record_label.py` 的向导只有 `printer_id`、`label_id` 两个业务字段；表单视图 `wizard/print_record_label.xml` 也只放出了这两个。其 Python 里残留的 `line_ids` / `label_no`（"# labels"）既没进视图，`print_label()` 也从不读取，因此原版永远只按选中记录各打一张——既不按产品数量，也无法指定总张数。

## 2. 依赖与安装

```python
'depends': ['printer_zpl2', 'stock']
```

- `printer_zpl2` — 被增强的向导与视图来源
- `stock` — 提供 `stock.lot`（序列号范围的基础模型）

> 依赖已最小化：本模块只依赖被增强的 `printer_zpl2` 与序列号基础模型 `stock`。原先的 `repair`、`mrp_zpl_label_print` 依赖均已移除——本模块对序列号的收集与打印逻辑是通用的；`res.users.zpl_printer_id` 只是"有则优先用"的增强项，`default_get` 里用字段存在性检查做了容错，没装提供该字段的模块时自动回退到通用向导的默认打印机选择。装/卸本模块不会再连带安装或卸载 MRP 打印模块。

全新安装（模块技术名从 `repair_order_zpl_label_print_advanced` 变更后需先卸载旧模块）：

```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -i printer_zpl2_wizard_enhanced --stop-after-init --log-level=info
```

后续升级（已安装，改代码后用 `-u`）：

```bash
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -u printer_zpl2_wizard_enhanced --stop-after-init --log-level=info
```

> `config/odoo.conf` 的 `addons_path` 已含 `addons/report-print-send`。

## 3. 文件地图

| 文件 | 作用 |
|---|---|
| `__manifest__.py` | 声明依赖与继承视图；不注册任何业务单据按钮 |
| `plan.md` | 开发目标、假设、数量策略设计、验证方案 |
| `agent.md` | 本文档 |
| `models/printing_label_zpl2.py` | `_inherit` ZPL 模板，覆写 `create_action` / `unlink_action` 为「按模板逐个」绑定/解绑 |
| `models/wizard_print_record_label.py` | 核心：`_inherit` 通用向导，字段 + `label_id` 域 + `default_get` / 打印计划 / `print_label` |
| `views/wizard_print_record_label_views.xml` | 继承通用向导表单，插入数量策略与范围分组 |
| `i18n/zh_CN.po` | 新增字段与提示的中文翻译 |

**已删除**（旧错误方案遗留）：`models/repair_order.py`、`views/repair_order_views.xml`、`wizards/`、`security/ir.model.access.csv`。

## 4. 核心工作流

### 4.1 入口（不变）

任意已通过 ZPL 模板「Add in the 'Action' menu」生成的**打印标签**菜单项。本模块没有添加任何新按钮、新动作。

### 4.2 继承的字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `quantity_source` | Selection | `per_quantity`（默认）/ `per_record` / `exact` |
| `copies_per_label` | Integer | 1–6，`@api.constrains` 校验；每单位/记录/序列号张数 |
| `exact_copies` | Integer | 1–999；`exact` 模式下的总张数 |
| `total_labels` | Integer | compute，实时显示本次将打印的总张数 |
| `available_lot_ids` | Many2many `stock.lot` | 候选序列号，`default_get` 填充 |
| `lot_ids` | Many2many `stock.lot` | 用户勾选的打印范围 |
| `use_lot_range` | Boolean | compute，模板绑定 `stock.lot` 时显示范围分组 |

沿用原向导的 `printer_id`、`label_id`、`active_model_id`。

### 4.3 数量策略（核心）

**打印对象与张数解耦**：对象由标签模板绑定的模型决定，张数由 `quantity_source` 决定。

| 模式 | 张数计算 | 典型场景 |
|---|---|---|
| `per_quantity`（默认） | Σ(每对象产品数量) × 份数 | 单据产品数量 2、份数 1 → **2 张** |
| `per_record` | 对象数 × 份数 | 每条记录固定张数；份数 1、1 条记录 → 1 张（原版兼容） |
| `exact` | 用户指定的总张数 | 产品 5 台但只想印 1 张 → 填 1 → **1 张** |

- `exact` 模式多选记录时，按顺序轮流作为打印对象（单记录即 N 张相同标签）。
- 份数在 `exact` 模式下隐藏、不参与计算。
- `total_labels` 与 `print_label()` 共用同一个 `_print_plan()`，预览张数与实际一致。

### 4.4 产品数量提取 `_record_quantity()`

1. `stock.lot` 恒返回 1（一个序列号代表一件）；
2. **模型专属字段优先**（`_MODEL_QUANTITY_FIELDS`）：`mrp.production` 取 `qty_producing`（生产单界面 `1.00 / 2.00` 中前面的"本单数量"），为 0/空时才回退 `product_qty`。这对应 Odoo 原生视图 `mrp_production_views.xml:252-258` 的显示顺序；
3. 再依次查通用数量字段：`product_qty`、`product_uom_qty`、`quantity`、`qty_done`、`qty`、`qty_ordered`、`product_qty_done`；取第一个正数；
4. 都没有则汇总明细行：`move_line_ids` / `move_ids` / `order_line` / `move_lines` / `line_ids`（递归，深度上限 3）；
5. 仍为 0 则回退 1。

现场若用自定义数量字段名，在 `_QUANTITY_FIELDS` 中补充；若某模型有特殊的"本单数量"字段，加到 `_MODEL_QUANTITY_FIELDS` 即可。

### 4.5 `default_get`（override）

1. `super()` 保留原版逻辑（只有一个打印机/标签时自动选）；
2. 用 `_collect_lots(active_model, active_ids)` 收集候选序列号，**对任意模型生效**：
   - **直接 lot 字段**：任意指向 `stock.lot` 的 m2o/m2m（含自定义字段）；
   - **关联下钻**：沿 o2m/m2m 递归（最多 4 层，带 `visited` 防环），如 `repair.order.move_ids → move_line_ids → lot_id`、`stock.picking.move_line_ids → lot_id`。跳过 `mail.*`/`ir.*`/`res.*`/`base.*`/`web.*` 及消息/活动字段。
3. 若用户设置了 `zpl_printer_id`，用它覆盖默认打印机。

### 4.6 打印计划 `_print_plan()`

```
objects = _print_objects()   # 模板绑定 stock.lot → 选中 lot_ids；否则 → context 选中记录
if quantity_source == 'exact':
    plan = [(objects[i % len(objects)], 1) for i in range(exact_copies)]
else:
    for obj in objects:
        count = quantity(obj) * copies  if per_quantity  else  copies
        plan.append((obj, count))
```

`print_label()` 遍历 plan 调用 `label.print_label(printer, record)`，并弹出成功通知（总张数）。无对象时抛 `UserError`。

### 4.7 模板可见性与动作菜单开关（17.0.6.0.0 新增）

**目标行为**：ZPL 模板只有点了「Add in the 'Action' menu」才在向导弹窗里出现；点「Remove from the 'Action' menu」就从下拉里消失，且**逐个模板互不影响**。

**为什么必须覆写**：`printer_zpl2` 原版两个方法是模型级的——
- `create_action()` 会把**同模型所有未绑定模板**一次性关联（实测：对 A 点添加，A、B 一起被绑定）；
- `unlink_action()` 直接 `action_window_id.unlink()` 删除共享动作，导致同模型**所有**模板一起失效（实测：对 A 点移除，B 与现有模板全部掉绑）。

**本模块覆写**（`models/printing_label_zpl2.py`）：
- `create_action()`：遍历 `self`，只把当前模板绑定到模型现存的打印动作（没有则用 `new_action` 建），已绑定的跳过；不再批量。
- `unlink_action()`：只 `write({'action_window_id': False})` 解绑当前模板，**保留动作记录**，其他模板不受影响；解绑后「添加」按钮重新出现。

**向导侧配套**（`wizard_print_record_label.py` + 视图）：
- **下拉筛选必须放在视图级 domain**（`views/wizard_print_record_label_views.xml`）：
  ```
  domain="[('action_window_id', '!=', False), ('model_id.model', '=', model)]"
  ```
  **这是关键**：many2one 下拉的域由 web client 通过 `fields_get` 计算，而那次调用的 context 只有 `{'uid': ...}`，**不含 `active_model`**。因此任何写在 Python 字段上的 `domain=lambda`（依赖 context）都拿不到模型 → 域退化为只过滤 `action_window_id` → **所有模型的模板全部列出**（实测复现：生产订单向导里出现调拨/库存移动行模板）。视图级 domain 在浏览器端用向导记录上持久化的 `model` 字段求值，不受 `fields_get` context 影响。
- `default_get()` 补填 `active_model_id`：模型解析链 `_context_model()` = `active_model` → `default_active_model_id`（ir.model ID 反查）→ `action_id`（动作 `binding_model_id` 反查）。四种入口（仅 active_model / 仅 default_active_model_id / 仅 action_id / 组合）均验证能补填出正确模型，向导记录的 `model`（related 字段）随之有值，视图 domain 即可正确求值。
- `default_get()` 的标签自动预选复用同一域，且仅在唯一命中时填入，避免预填不可见模板。

> 依赖模型仍只有 `printer_zpl2` + `stock`；本改动不新增按钮、不新增依赖。

### 4.8 视图继承

继承 `printer_zpl2.view_wizard_print_product_label_form`，在 `<footer>` 前插入：

- `Print Options` → `quantity_source`、`copies_per_label`（`exact` 时隐藏）、`exact_copies`（非 `exact` 时隐藏）、`total_labels`（只读）
- `Print Range (Lots / Serial Numbers)` → `lot_ids`（`invisible="not use_lot_range"`）

原版「打印机 / 标签」字段的位置与样式不变。

## 5. 关键设计决策

1. **改向导，不加按钮**：用户已经在 ZPL 模板上用了「添加到动作菜单」，增强必须作用在它打开的向导上。
2. **继承而非复制**：`_inherit` + 视图继承，不复制 `printer_zpl2` 的字段或方法。
3. **对象与张数解耦**：模板模型决定打印对象，数量策略决定张数——这样才能同时支持"按数量"和"精确张数"而互不干扰。
4. **默认 `per_quantity`**：直接满足"数量 2、份数 1 应打 2 张"的直觉；要原版行为选 `per_record`。
5. **预览与执行同源**：`total_labels` 复用 `_print_plan()`，所见即所打。
6. **收集通用，范围仍由模板决定**：序列号从任何关联 `stock.lot` 的模型收集；只有绑定 `stock.lot` 的模板才显示并使用 `lot_ids`（ZPL 组件按被打印对象渲染）。
7. **不绑定业务模型**：模块名与依赖都不含 `repair`，任何通过 `printer_zpl2` 添加「打印标签」的模型都受益。

## 6. 已知假设与风险

- **最大假设**：「不同序列号」= `stock.lot`。现场若用自定义字段（非指向 `stock.lot`），扩展 `_direct_lot_fields()` 即可。
- 产品数量靠字段名约定提取；现场自定义数量字段需补 `_QUANTITY_FIELDS`。
- 本地库无 `stock.lot` 数据，`lot_ids` 用临时数据验证；真实链路需现场确认。
- 本模块增强的是**通用向导**，对 `printer_zpl2` 添加的任何模型的「打印标签」动作都会显示新字段；未关联序列号时 `lot_ids` 为空、行为与原版一致。
- `exact` 模式多选记录时按序轮流作为打印对象；若需逐条指定张数，需另做行式明细向导。
- 卸载本模块后，通用向导恢复原版（仅打印机 + 标签）。

## 7. 验证与排错

```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0
venv/bin/python -m py_compile addons/report-print-send/printer_zpl2_wizard_enhanced/{__manifest__,__init__}.py \
  addons/report-print-send/printer_zpl2_wizard_enhanced/models/*.py
```

Odoo shell 验证要点：

```python
W = env['wizard.print.record.label']
ctx = {'active_model': 'mrp.production', 'active_ids': [1]}
w = W.with_context(**ctx).create({
    'printer_id': printer.id, 'label_id': template.id,
    'quantity_source': 'per_quantity', 'copies_per_label': 1,
})
print('总数预览:', w.total_labels)   # 数量 2 → 2
# 非维修模型也能收集序列号
print(W.with_context(active_model='stock.picking', active_ids=[1]).default_get(['lot_ids']))
```

常见问题：

| 现象 | 原因 / 处理 |
|---|---|
| 「打印标签」弹窗没有新字段 | 视图未升级，执行 `-u printer_zpl2_wizard_enhanced` |
| 份数框不显示 | 当前是 `exact` 模式，切到按数量/按记录 |
| 打印张数和预期不符 | 先看 `total_labels` 预览：按数量=数量×份数；精确模式=填写的总张数 |
| 新建的模板在向导里看不到 | 该模板未点「Add in the 'Action' menu」；域只显示已绑定动作的模板 |
| 点「移除」后同模型其它模板一起消失 | 用的是原版 `printer_zpl2` 行为；升级到 17.0.6.0.0，本模块已改为逐个解绑且不删动作 |
| 从菜单进向导「标签」下拉为空 | 确认 `default_active_model_id` 在动作 context 中；本模块已从它反查模型兜底 |
| 范围分组不显示 | 当前模板绑定的不是 `stock.lot`，改用 `stock.lot` 模板 |
| 打印机不是个人资料的值 | 个人资料「ZPL Label Printing」分组未设 `zpl_printer_id` |
| 总张数为 0 | 未选中记录/序列号，或上下文缺 `active_ids` |
