# ZPL 通用打印向导增强模块 — 开发计划

## 1. 目标（已修正）

**不是在维修单上新增按钮**，而是增强 `printer_zpl2` 已经提供的「打印标签」向导。

`printer_zpl2` 的 ZPL 模板表单上有一个 **Add in the 'Action' menu** 按钮（`create_action()`），它会创建一个绑定指定模型（如 `repair.order`、`mrp.production`、`stock.picking`）的 `ir.actions.act_window`，指向 `wizard.print.record.label`。用户在该模型「操作」菜单下看到的「打印标签」就是它。

本模块通过 `_inherit = 'wizard.print.record.label'` **增强这个既有向导**，让同一个「打印标签」菜单项同时支持：

- 标签模板选择（由 `printer_zpl2` 原有提供）
- **三种数量计算方式**：按产品数量 / 按记录或序列号 / 精确指定总张数
- 份数（每单位/记录 1–6）与**总张数实时预览**
- 打印范围选择（按批次/序列号，任意关联 `stock.lot` 的模型）
- 打印机默认取个人资料的 `zpl_printer_id`（若提供该字段的模块已安装，否则回退通用向导默认选择）
- 模板可见性跟随动作菜单开关：只有点「Add in the 'Action' menu」的模板才出现在向导弹窗；「Remove」只解绑当前模板

用户不需要换入口，也不需要新按钮。

## 2. 为什么原来的方案不对

最初的目标写成「在维修单表单上提供增强打印按钮，打开一个新向导」，这会导致：

- 业务单据上出现两个功能重叠的按钮（`Prnt ZPL Labels` 和新的增强按钮）；
- 用户已经在 ZPL 模板上点了「添加到动作菜单」，那个「打印标签」菜单项仍然是残缺的；
- 增强只作用于新按钮，没有解决通用向导本身缺字段的问题。

修正后的方案直接改造通用向导，**一次修改，所有通过 `printer_zpl2` 添加的「打印标签」动作都受益**。

## 3. 关键假设

1. 「不同序列号」= `stock.lot`（Odoo 中批次/序列号统一模型）。
2. 候选序列号按**通用规则**从当前选中记录收集，不对任何模型写死：
   - 直接字段：模型上任意指向 `stock.lot` 的 many2one / many2many；
   - 关联下钻：沿 one2many / many2many 关系递归（最多 4 层，带访问集合防环），从关联的库存移动行取 `lot_id`。
3. **打印对象由模板模型决定**：
   - 模板绑定 `stock.lot` → 对象为勾选的序列号；
   - 模板绑定其他模型（如 `repair.order`、`mrp.production`）→ 对象为当前选中的业务记录。
4. **张数由数量策略决定**（与对象解耦）：
   - `per_quantity`（默认）：张数 = Σ(每对象产品数量) × 份数。数量 2、份数 1 → 2 张，解决用户场景 A。
   - `per_record`：张数 = 对象数 × 份数（原版兼容行为）。
   - `exact`：张数 = 用户指定的总张数，忽略单据数量。数量 5、指定 1 → 1 张，解决用户场景 B。多选记录时按顺序轮流作为打印对象。
5. 产品数量提取：模型专属字段优先（`mrp.production` → `qty_producing`，即生产单界面 `1.00 / 2.00` 中前面的"本单数量"，而非计划总量 `product_qty`），再查通用字段（`product_qty`、`product_uom_qty`、`quantity` 等），找不到时汇总明细行（`move_line_ids` / `move_ids` / `order_line`），再找不到回退 1；`stock.lot` 恒为 1。
6. 本地库 `ot_17.0_111366` 无真实序列号数据，需用临时数据验证。

## 4. 模块设计

- **模块名**：`printer_zpl2_wizard_enhanced`（通用命名，明确是增强 `printer_zpl2` 的向导，不绑定任何业务模型）。
- **依赖**：
  - `printer_zpl2` — 提供被增强的向导与视图
  - `stock` — 提供 `stock.lot`（序列号范围的基础模型）

> 依赖已最小化：`repair` 与 `mrp_zpl_label_print` 均不再是依赖。序列号收集与打印逻辑是通用实现；`res.users.zpl_printer_id` 改为"有则优先用"（通过字段存在性检查容错），没装提供该字段的模块时回退到通用向导的默认打印机选择。装/卸本模块不再连带影响 MRP 打印模块。

**文件结构**：

```
printer_zpl2_wizard_enhanced/
├── __manifest__.py
├── __init__.py
├── plan.md
├── agent.md
├── models/
│   ├── __init__.py
│   └── wizard_print_record_label.py   # _inherit 增强向导
├── views/
│   └── wizard_print_record_label_views.xml  # 继承通用向导视图
└── i18n/
    └── zh_CN.po
```

## 5. 字段设计（继承后新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| `quantity_source` | Selection | `per_quantity`（默认）/ `per_record` / `exact` |
| `copies_per_label` | Integer | 1–6，`@api.constrains` 校验；每单位/记录/序列号张数，`exact` 模式下隐藏 |
| `exact_copies` | Integer | 1–999；`exact` 模式下填写的总张数 |
| `total_labels` | Integer | compute，实时显示本次将打印的总张数 |
| `available_lot_ids` | Many2many `stock.lot` | 普通字段，`default_get` 中填充候选 |
| `lot_ids` | Many2many `stock.lot` | 用户勾选的打印范围，domain 限候选集合 |
| `use_lot_range` | Boolean | compute，模板绑定 `stock.lot` 时显示范围分组 |

原有字段 `printer_id`、`label_id`、`active_model_id` 完全沿用 `printer_zpl2`。

## 6. 核心逻辑

### 6.1 `default_get`（override）

1. 先 `super().default_get()`，保留原版的打印机/标签自动选择；
2. 用通用收集器 `_collect_lots` 从 context 的 `active_model` / `active_ids` 抓取序列号，填入 `available_lot_ids` 与 `lot_ids`；
3. 若当前用户设置了 `zpl_printer_id`，覆盖默认打印机。

### 6.2 打印计划 `_print_plan()`

```
objects = _print_objects()              # 由模板模型决定
if quantity_source == 'exact':
    plan = [(objects[i % len(objects)], 1) for i in range(exact_copies)]
else:
    for obj in objects:
        if quantity_source == 'per_quantity':
            count = max(1, quantity(obj)) * copies
        else:                            # per_record
            count = copies
        plan.append((obj, count))
total_labels = Σ count
```

`print_label()` 遍历 plan 调用 `label.print_label(printer, record)`；`total_labels` 复用同一计划做预览，保证「看到的张数」＝「实际打印的张数」。

### 6.3 视图继承

继承 `printer_zpl2.view_wizard_print_product_label_form`，在 `<footer>` 前插入：

- `Print Options` 分组：`quantity_source`、`copies_per_label`、`exact_copies`、`total_labels`
- `Print Range (Lots / Serial Numbers)` 分组：`lot_ids`（`use_lot_range=False` 时隐藏）

原版的两个字段（打印机、标签）保持原位置和样式。

## 7. 验证方案

1. 静态校验 Python / XML；
2. `-i printer_zpl2_wizard_enhanced` 全新安装（因模块技术名已变更，需卸载旧模块后重装）；
3. Odoo shell 验证（mock `print_label` 计数）：
   - 新字段存在，默认 `quantity_source=per_quantity`、`total_labels` 正确；
   - **数量 2 + 份数 1 → 2 张**（用户场景 A）；
   - **数量 5 + `exact` 总张数 1 → 1 张**（用户场景 B）；
   - `per_record` + 份数 1 × 1 条记录 → 1 张（向后兼容）；
   - 序列号模板 + 2 个序列号 → 2 张；非维修模型（`stock.move`）也能收集到序列号；
   - 个人资料改 `zpl_printer_id` 后 `default_get` 立即跟随；
4. 确认业务单据表单上没有新增按钮，只有原有的「打印标签」菜单项。

## 8. 风险与后续

- 序列号收集对所有关联 `stock.lot` 的模型生效；未关联时 `lot_ids` 为空、行为与原版一致。
- 产品数量是从字段约定推断的；若现场用自定义数量字段名，在 `_record_quantity()` 的 `_QUANTITY_FIELDS` 中补充即可。
- `exact` 模式多选记录时按序轮流作为打印对象；若需要「给每条记录分别指定张数」，需另做行式明细向导，当前版本刻意保持简单。
- 卸载本模块后，`printer_zpl2` 的通用向导恢复原版（只有打印机 + 标签）。
