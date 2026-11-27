# AGENT 指南 — repair_auto_print（Odoo 17 维修完成自动打印）

> 面向后续 AI / 维护者。修改本模块前先读本文件，并留意 §4 的双通道打印机制 与 §7 的已知坑。

---

## 1. 模块做什么

给 `repair.order`（维修单）在**完成维修时**自动打印三类文档，无需人工点击：

1. **维修单**（PDF 原生报表 或 **ZPL II 自定义标签直推**，17.0.1.2.0 新增）
2. **修复商品标签**（PDF 4x12 走 `product.label.layout` 向导；或 ZPL II 自定义模板直推）
3. **修复 lot/序列号标签**（PDF 走 `stock.action_report_lot_label`；或 ZPL II 走 `stock.label_lot_template` / 自定义模板直推）

- 模块名：`repair_auto_print` · 版本 `17.0.1.1.2` · 分类 `Manufacturing` · 许可 `OPL-1`
- 作者：metaodoo.com（**非 OCA 上游模块**，本地商业插件）
- 定位：`application=False`、`auto_install=False`，纯业务触发器；**不依赖** `printing_auto_base`，所有规则字段由本模块自管
- 底层能力：
  - `printer_zpl2` / `printer_zpl2_enhanced`：`printing.label.zpl2` 模板 + `_generate_zpl2_data()`
  - `base_report_to_label_printer`：用户默认标签打印机 `default_label_printer_id`
  - `printing.printer.print_document(doc_format="raw")`：raw ZPL 字节流推 CUPS

---

## 2. 依赖

| 类型 | 模块 / 模型 | 说明 |
|---|---|---|
| manifest 声明 | `repair` | 原生维修单模型 |
| manifest 声明 | `printer_zpl2` | `printing.label.zpl2` 模板、`_generate_zpl2_data()` |
| manifest 声明 | `printer_zpl2_enhanced` | `printing.label.zpl2.user.action` 用户级打印机绑定；商品表单视图继承 |
| manifest 声明 | `base_report_to_label_printer` | `res.users.default_label_printer_id` |
| 隐含使用 | `stock.group_production_lot` | lot/SN 自动打印只对该组用户生效 |
| 隐含使用 | `product.label.layout` | Odoo 原生产品标签打印向导（PDF 4x12） |

> ⚠️ 本模块**不依赖** `printing_auto_base`，与 `printing.auto` 规则引擎无关。打印配置直接走 `stock.picking.type` + `product.template` 上的自定义字段。

---

## 3. 文件地图

```
repair_auto_print/
├── __manifest__.py                             # 元数据、depends、views
├── __init__.py                                 # import models
├── models/
│   ├── __init__.py
│   ├── repair_order.py                         # 核心：覆写 action_repair_done + 双通道打印编排
│   ├── stock_picking_type.py                   # 操作类型上的开关、模板绑定、份数
│   └── product_template.py                     # 商品级覆盖字段（模板+份数）
├── views/
│   ├── stock_picking_type_views.xml           # 维修操作类型的 "Hardware" 页签
│   └── product_template_views.xml             # 商品表单 ZPL Labels 页签内的 "Repair Labels" 分组
├── tests/
│   └── test_repair_auto_print.py               # 自动化测试
├── i18n/
│   ├── repair_auto_print.pot
│   └── zh_CN.po
└── README.rst
```

**没有**：菜单 / act_window / security/ir.model.access.csv（继承已有模型，不需要新表）/ wizard。

---

## 4. 关键实现细节（改动前务必遵守）

### 4.1 入口（覆写原生按钮）

`models/repair_order.py` 的 `action_repair_done()`：

```python
def action_repair_done(self):
    result = super().action_repair_done()             # ① 先让原生逻辑跑完（维修单状态变 done）
    report_actions = self._get_autoprint_done_report_actions()
    if not report_actions:
        return result                                 # ② 没要打的内容 → 返回原生动作
    return {
        "type": "ir.actions.client",
        "tag": "do_multi_print",                     # ③ 前端多报表打印弹窗
        "context": {},
        "params": {"reports": report_actions},
    }
```

**关键约束**：
- `super()` 必须先调，否则维修单状态没切，后续报表渲染的是旧数据。
- 返回的是 **客户端动作** `do_multi_print`（由 `base_report_to_printer` 的 JS action manager 接管），不是普通的 `ir.actions.act_window`。
- 只打包**走浏览器的报表**；ZPL II 已在后端直推 CUPS，不进这个列表。

### 4.2 双通道打印机制（核心）

`_get_autoprint_done_report_actions()` 的执行顺序：

```
① _print_done_zpl2_labels()                         # 后端直推商品/lot ZPL II（不走浏览器）
   · 逐维修单循环
   · 检查 picking_type_id.auto_print_done_repair_product_labels / auto_print_done_repair_lot
   · 解析模板 → 解析渲染记录 → 解析打印机 → 拼接 N 份 raw ZPL → printer.print_document(doc_format="raw")
   · 返回 (direct_product_repairs, direct_lot_repairs)：已被后端处理的维修单集合

② 维修单本身（17.0.1.2.0 新增双通道）
   · 过滤 eligible 维修单：操作类型开关开 OR 商品级有 repair_order_zpl2_label_id+copies>0
   · 逐维修单调 _print_repair_order_zpl_labels()：
       - 解析商品级 OR 操作类型级 ZPL 模板
       - 解析到模板 → _print_done_zpl2_label() 直推 CUPS，记录到 direct_repair_order_repairs
       - 解析不到模板 → 返回 False，进入 standard_pdf_repairs
   · standard_pdf_repairs → repair.action_report_repair_order.report_action() 进 do_multi_print

③ 收集浏览器端打印的 report_actions（剩余部分）
   · 商品标签 PDF：filtered(auto_print_done_repair_product_labels AND product_id)
       - 先减去 direct_product_repairs（避免重复打）
       - 按 picking_type_id.repair_product_label_to_print 分组
       - 用 product.label.layout 向导（print_format="4x12" if "pdf" else "zpl"）
   · lot 标签 PDF：filtered(auto_print_done_repair_lot AND lot_id AND 用户在 stock.group_production_lot)
       - 先减去 direct_lot_repairs
       - 按 done_repair_lot_label_to_print 分组
       - PDF → stock.action_report_lot_label；ZPL（浏览器）→ stock.label_lot_template
```

**已直推的维修单必须从浏览器打印列表里剔除**（`- direct_product_repairs`、`- direct_lot_repairs`、`- direct_repair_order_repairs`），否则会重复打。

### 4.3 模板解析（`_resolve_done_zpl2_label`）

```python
product_template = self.product_id.product_tmpl_id
# 模板：商品专用 > 操作类型默认
label = product_template[f"{prefix}_zpl2_label_id"] or self.picking_type_id[f"{prefix}_zpl2_label_id"]
# 份数：商品专用 (>0) > 操作类型默认
product_copies = product_template[f"{prefix}_zpl2_copies"]
copies = product_copies if product_copies > 0 else self.picking_type_id[f"{prefix}_zpl2_copies"]
```

**优先级约定**：商品模板字段为 0 / 空 = "继承操作类型"，**不是"禁用"**。要禁用某商品的自动打印，必须去操作类型层把对应开关取消，或在商品级 `copies` 保持 0 且不选模板。

### 4.4 渲染记录映射（`_get_done_zpl2_record`）

ZPL II 模板的 `model_id.model` 决定渲染时传哪条记录：

| 模板绑定模型 | 传入的记录 |
|---|---|
| `repair.order` | 当前维修单 |
| `product.product` | `repair.product_id` |
| `product.template` | `product_id.product_tmpl_id` |
| `stock.lot` | `repair.lot_id` |

不在上表的模型直接抛 `UserError("unsupported model: ...")`。新增支持模型时，改 `records` 字典即可。

### 4.5 打印机解析（`_get_done_zpl2_printer`）

三级 fallback：

```
① printing.label.zpl2.user.action  (user+label 绑定, active=True)
② printing.label.zpl2.default_printer_id  (模板自带默认)
③ env.user.default_label_printer_id  (用户个人偏好)
```

**兜底校验**：
- 三级都拿不到打印机 → 抛 `UserError`，明确提示去哪配。
- 拿到的 `printer.status != "available"` → 抛 `UserError`，把状态翻译成中文可读值。

> ⚠️ 本模块**不在自己的模型上配打印机**。要改打印机，要么改 ZPL 模板默认打印机，要么改用户偏好的 `default_label_printer_id`，要么建 `printing.label.zpl2.user.action`。

### 4.6 ZPL 字节流拼接（`_print_done_zpl2_label`）

```python
zpl_content = b"".join(label._generate_zpl2_data(record) for _copy in range(count))
printer.print_document(report=None, content=zpl_content, doc_format="raw")
```

- **N 份在一次 raw 字节流里拼好**，一次性发送，避免多次握手。
- `doc_format="raw"` 是 ZPL 打印机的关键，不能改成 PDF。

### 4.7 标签份数按数量放大（产品 + lot 都乘）

`_print_done_zpl2_labels()` 里：

```python
count = math.ceil(repair.product_qty) * copies
```

维修了 3 件、每份 2 张 → 实际打 6 张标签。**产品标签和 lot 标签都按此规则**（17.0.1.2.0 起产品标签也乘数量；之前只有 lot 乘）。不要改成只按份数乘，否则多件维修会少打。

### 4.8 配置字段一览（两层）

**`stock.picking.type`（操作类型，`code='repair_operation'` 时才显示 Hardware 页签）**：

| 字段 | 类型 | 作用 |
|---|---|---|
| `auto_print_done_repair_order` | Boolean | 完成时打印维修单 |
| `repair_order_label_to_print` | Selection(pdf/zpl) | 维修单走 PDF 还是 ZPL（17.0.1.2.0 新增） |
| `repair_order_zpl2_label_id` | M2O `printing.label.zpl2` | 默认维修单 ZPL 模板（模型 = repair.order） |
| `repair_order_zpl2_copies` | Integer 1–10 | 默认份数 |
| `auto_print_done_repair_product_labels` | Boolean | 打印修复商品标签 |
| `repair_product_label_to_print` | Selection(pdf/zpl) | 商品标签走 PDF 还是 ZPL |
| `repair_product_zpl2_label_id` | M2O `printing.label.zpl2` | 默认商品 ZPL 模板（模型 ∈ repair.order/product.product/product.template） |
| `repair_product_zpl2_copies` | Integer 1–10 | 默认份数 |
| `auto_print_done_repair_lot` | Boolean | 打印 lot/SN 标签（需 `stock.group_production_lot`） |
| `done_repair_lot_label_to_print` | Selection(pdf/zpl) | lot 标签走 PDF 还是 ZPL |
| `done_repair_lot_zpl2_label_id` | M2O `printing.label.zpl2` | 默认 lot ZPL 模板（模型 = stock.lot） |
| `done_repair_lot_zpl2_copies` | Integer 1–10 | 默认份数 |

**`product.template`（商品级覆盖）**：

| 字段 | 类型 | 作用 |
|---|---|---|
| `repair_order_zpl2_label_id` | M2O | 该商品专属维修单 ZPL 模板（模型 = repair.order） |
| `repair_order_zpl2_copies` | Integer 0–10 | 0 = 继承；>0 覆盖 |
| `repair_product_zpl2_label_id` | M2O | 该商品专属维修产品标签模板（空则用操作类型默认） |
| `repair_product_zpl2_copies` | Integer 0–10 | 0 = 继承；>0 覆盖 |
| `done_repair_lot_zpl2_label_id` | M2O | 该商品专属 lot 标签模板 |
| `done_repair_lot_zpl2_copies` | Integer 0–10 | 同上 |

**校验**：
- 操作类型：份数必须 1–10（`@api.constrains`）
- 商品模板：份数必须 0–10（0 是合法的"继承"语义）

### 4.9 视图注入点

**`stock_picking_type_views.xml`**：
- 继承 `stock.view_picking_type_form`
- 在 `//page[@name='hardware']` 之后插入新页签 `repair_hardware`
- **`invisible="code != 'repair_operation'"`**：只对维修操作类型显示
- 子字段用 `invisible="not auto_print_done_..."` 控制可见性，未启用时界面干净

**`product_template_views.xml`**：
- 继承 `printer_zpl2_enhanced.view_product_template_form_zpl2_labels`
- 在 `//page[@name='zpl_labels']` 内追加 `<group name="repair_zpl2_label_section">`
- 同时把 `zpl_labels` 页签的可见性放宽为 `type not in ('consu', 'product')` 时也隐藏

---

## 5. 与兄弟模块的边界

| 模块 | 关系 |
|---|---|
| `repair_order_zpl_label_print` | 维修单上**手动**点按钮打 ZPL 标签的向导；本模块是**完成时自动**打，两者可共存 |
| `printing_auto_base` | **无关**。本模块不走 `printing.auto` 规则引擎 |
| `printer_zpl2_enhanced` | 提供商品表单 ZPL Labels 页签 + 用户级打印机绑定 |
| `base_report_to_label_printer` | 提供 `default_label_printer_id` 用户偏好字段 |
| `stock_mrp_auto_print` | 兄弟模块（生产订单 + 库存），结构相似但业务模型不同；不要顺手重构那边 |

---

## 6. 安装 / 升级

```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0

# 首次安装
unset PYTHONPATH BASH_ENV NODE_OPTIONS PYTHONDONTWRITEBYTECODE
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -i repair_auto_print --stop-after-init --http-port=0 --gevent-port=0 --log-level=info

# 改代码后升级
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -u repair_auto_print --stop-after-init --http-port=0 --gevent-port=0 --log-level=info
```

---

## 7. 已知问题 / 维护注意

- **ZPL 模板不在"报表列表"里**：它是 `printing.label.zpl2` 对象，靠 `stock.picking.type` / `product.template` 上的 4 个 M2O 字段绑定，不是 `ir.actions.report`。新增模板后必须去操作类型（或商品）表单选它，否则本模块不会发现。
- **打印机不在本模块配置**：走 `printing.label.zpl2.user.action` → `default_printer_id` → `user.default_label_printer_id` 三级。排查"没打到预期打印机"时按这个顺序查。
- **商品级 `copies=0` 不是"禁用"**：是"继承操作类型"语义。要禁用某商品必须清空模板 + 在操作类型层取消开关，否则会落到操作类型默认值继续打。
- **lot 份数已乘 `product_qty`**：如果现场反馈"打多了"，先看 `product_qty` 是否被多算（如 UoM 换算）。
- **浏览器端 report_actions 必须剔除已直推的维修单**：`direct_product_repairs` / `direct_lot_repairs` 这两个 recordset 是防重复打的关键，重构时不能丢。
- **`do_multi_print` 客户端动作**：前端依赖 `base_report_to_printer` 的 JS action manager；如果那个模块的 JS 没加载，前端点击完成会无反应。这不是本模块 bug。
- **`UserError` 是硬阻断**：本模块所有错误（无打印机、打印机离线、模板模型不支持）都直接抛 `UserError`，会让"完成维修"按钮失败。没有 `printing_auto_base` 那种 savepoint + `action_on_error=log` 的容错机制。要做容错需要自行包 try/except。
- **OPL-1 许可**：与 OCA AGPL 模块混用前注意许可兼容。
- **Odoo 17 语法**：不要用 v18+ 的 `<list>`、`aggregator=`、SQL 类；字符串翻译用 `_()`。
- **`addons_path` 已配置**：`17.0/config/odoo.conf` 已含 `addons/report-print-send`。

---

## 8. 手工验证路径

1. 在 ZPL 模板设计器里建两个模板：
   - 商品标签模板（绑定模型 = `product.product` 或 `repair.order`）
   - lot 标签模板（绑定模型 = `stock.lot`）
2. 给当前用户设置 `default_label_printer_id`（用户偏好 → Label Printer），或给 ZPL 模板设 `default_printer_id`。
3. 进入 **Inventory → Configuration → Operations Types → 维修操作类型**：
   - 勾 `auto_print_done_repair_product_labels`，选商品 ZPL 模板
   - 勾 `auto_print_done_repair_lot`，选 lot ZPL 模板（需 `stock.group_production_lot`）
4. 打开一张维修单 → 点 "完成" → 检查：
   - ZPL 标签是否直接出现在打印机（不弹窗）
   - 维修单 PDF 是否弹出浏览器打印对话框
   - 已直推 ZPL 的维修单**不应**再出现在浏览器打印列表里

---

## 9. 协作约定

- 分支 `17.0`；提交信息用中文 + Conventional 前缀（如 `fix(repair_auto_print): ...`）。**未经明确要求不要提交/推送**。
- 改动保持最小、可验证；不要顺手重构兄弟的 `repair_order_zpl_label_print` / `stock_mrp_auto_print`。
- 若改了配置字段或双通道逻辑，请同步更新本文件 §4 / §7 对应章节。
