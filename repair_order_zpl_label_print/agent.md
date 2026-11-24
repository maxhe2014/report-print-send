# AGENT 指南 — repair_order_zpl_label_print（Odoo 17 维修单 ZPL 标签打印）

> 面向后续 AI / 维护者。修改本模块前先读本文件，并留意 §5 的隐藏依赖与 §6 的已知问题。

---

## 1. 模块做什么

给 `repair.order`（维修单）增加 **ZPL 标签打印**入口：维修单表单头部出现「Print ZPL Labels」按钮，点击弹出向导，选择标签模板 / 打印机 / 份数后，把 ZPL 指令直接发送到网络打印机。

- 模块名：`repair_order_zpl_label_print` · 版本 `17.0.1.0.0` · 分类 `Maintenance` · 许可 `LGPL-3`
- 定位：`application=False`、`auto_install=False`，属于 OCA `report-print-send` 仓库下的**自定义扩展模块**（非上游 OCA 模块，随 `mrp_zpl_label_print` 一次提交引入，见 commit `3a022e2`）。
- 底层能力来自 `printer_zpl2`：`printing.label.zpl2` 模板 + `_generate_zpl2_data()` / `print_label()`，通过 `printing.printer.print_document(..., doc_format="raw")` 发送原始 ZPL。

### 核心工作流

```
维修单表单「Print ZPL Labels」按钮
  → repair.order.action_open_zpl_label_wizard()
  → 打开 print.repair.zpl.label.wizard（target='new' 弹窗，context 带 default_repair_id）
  → default_get()：默认维修单 + 默认标签模板
  → _compute_default_printer()：按「用户+模板配置 → 用户默认 ZPL 打印机」解析打印机
  → action_print_labels()
      · 模板 model 必须为 repair.order
      · 份数 = copies_per_label × repair.product_qty（print_exact_quantity=True 时直接取 copies_per_label）
      · 逐张循环 print_label(..., copies=1)
      · 保存/更新 printing.label.zpl2.configuration（用户+模板 → 打印机）
      · display_notification 成功提示
```

---

## 2. 依赖

| 类型 | 模块 / 模型 | 说明 |
|---|---|---|
| manifest 声明 | `repair`, `printer_zpl2`, `mrp_zpl_label_print` | `mrp_zpl_label_print` 提供 `res.users.zpl_printer_id` 默认打印机字段 |
| 依赖（2026-11-24 已补齐） | `stock_picking_zpl_label_print` | 提供 `printing.label.zpl2.configuration` 模型；原先未声明，现已写入 `depends` |
| 使用的基础模型 | `printing.label.zpl2`, `printing.printer`, `printing.label.zpl2.configuration`, `res.users`, `repair.order` | 前两者来自 `printer_zpl2`；配置模型来自 `stock_picking_zpl_label_print` |

---

## 3. 文件地图

```
repair_order_zpl_label_print/
├── __manifest__.py                             # 元数据、depends、data 加载顺序
├── __init__.py                                 # import models, wizards
├── models/
│   ├── __init__.py
│   └── repair_order.py                         # repair.order 扩展：action_open_zpl_label_wizard()
├── wizards/
│   ├── __init__.py
│   ├── print_repair_zpl_label_wizard.py        # 核心：向导字段 + 默认打印机/模板 + 打印逻辑
│   └── print_repair_zpl_label_wizard_views.xml # 向导表单视图
├── views/
│   └── repair_order_views.xml                  # 继承维修单表单，header 内加打印按钮
├── security/
│   └── ir.model.access.csv                     # 向导 ACL（group_user / group_system 全 CRUD）
└── i18n/
    └── zh_CN.po                                # 中文翻译（含已失效条目，见 §6）
```

**没有** `tests/`、`README.rst`、`static/description`，也没有菜单项——入口只在维修单表单上。

---

## 4. 关键实现细节（改动前务必遵守）

### 4.1 入口按钮
- `views/repair_order_views.xml`：继承 `repair.view_repair_order_form`，用 xpath `//header position="inside"` 注入按钮。
- 按钮 `type="object"` 调用 `action_open_zpl_label_wizard()`，`class="btn-primary"`，**带 `groups="stock.group_production_lot"`**——只有「Manage Lots / Serial Numbers」组的用户能看到。改权限需同步改这里。
- ⚠️ 2026-11-24 实测：`ot_17.0_111366` 库里该组**有 0 个用户**（连管理员 `admin` 也不在），所以维修单上按钮对所有人不可见。若用户反馈看不到按钮，先查 `env.ref('stock.group_production_lot').users`；要么给用户加组，要么去掉这个 `groups` 限制。

### 4.2 向导字段 `print.repair.zpl.label.wizard`（TransientModel）
| 字段 | 类型 | 要点 |
|---|---|---|
| `repair_id` | Many2one `repair.order` | `readonly=True`，由 context `default_repair_id` 注入 |
| `printer_id` | Many2one `printing.printer` | 可编辑；`default_get` 中默认取 `user.zpl_printer_id`（个人资料） |
| `label_template_id` | Many2one `printing.label.zpl2` | `required=True`，domain 限定 `model_id.model == 'repair.order'` 且 `active=True` |
| `copies_per_label` | Integer | 默认 1，每张标签份数 |
| `print_exact_quantity` | Boolean | 默认 False；True 时不乘 `product_qty` |

### 4.3 默认打印机解析（2026-11-24 已修复）
`default_get` 直接取 `self.env.user.zpl_printer_id` 作为默认值，用户在向导里也可以手动改。
原先的 `_compute_default_printer` 会优先读 `printing.label.zpl2.configuration` 并 `continue`
跳过个人资料设置，且打印成功后又写回该表，导致改个人资料不生效——该计算字段已删除。
注意个人资料里另一个字段 `printing_printer_id`（Printing 分组）本模块不读取，不要改错。

### 4.4 默认模板解析顺序（`default_get`）
1. 查该用户「model 为 repair.order」的最近一条配置（按 `write_date desc`），取 `label_id`；
2. 无配置则取第一个可用的 `repair.order` 标签模板（按 `name` 排序，`limit=1`）。

### 4.5 打印逻辑（`action_print_labels`）
- 前置校验：无打印机 → `UserError`；无模板 → `UserError`；模板 `model_id.model != 'repair.order'` → `UserError`；无 `repair_id` → `UserError`。
- **份数计算**：`print_exact_quantity=True` → `copies_per_label`；否则 `copies_per_label × int(repair.product_qty)`（`product_qty` 不存在或 ≤0 时按 1 处理）。
- **逐张打印**：`for i in range(total_copies)` 每次调用 `label_template_id.print_label(printer, repair, copies=1)`。基础 `print_label` 签名是 `print_label(printer, record, page_count=1, **extra)`，`copies=1` 落入 `**extra` 实际被忽略——**份数完全由外层循环控制**，不要误以为 `copies` 参数生效。
- 打印成功后仍会 upsert 用户+模板的 `printing.label.zpl2.configuration`，但**只用于记住上次模板**，不再作为默认打印机来源（见 §4.3）。
- 全程包在 `try/except Exception` 中：`_logger.error` 记录原始异常后抛 `UserError("Label printing failed: ...")`。排障请看 `17.0/logs/odoo.log`。
- 不同于兄弟模块 `mrp_zpl_label_print`：那边用 `_generate_zpl2_data()` 批量拼接后一次 `print_document(..., format='raw')`；本模块选择逐张 `print_label`。两套风格并存，**不要混用**。

### 4.6 安全
- `security/ir.model.access.csv` 给向导模型 `print.repair.zpl.label.wizard` 在 `base.group_user` 和 `base.group_system` 下都开了全 CRUD（TransientModel 常规做法）。
- 视图层靠 `stock.group_production_lot` 控制按钮可见性，模型层未对打印动作做额外权限校验。

---

## 5. 依赖说明（2026-11-24 已修复）

原先 `default_get` / `action_print_labels` 两处使用 `self.env['printing.label.zpl2.configuration']`，
但该模型由兄弟模块 `stock_picking_zpl_label_print` 提供却未列入 `depends`，属于隐藏依赖。
现已将 `stock_picking_zpl_label_print` 加入 `__manifest__.py` 的 `depends`，安装时自动带上。
（`_compute_default_printer` 已删除，不再使用该配置表作为打印机来源。）

---

## 6. 已知问题 / 维护注意

- **「个人资料改了打印机不生效」已于 2026-11-24 修复**：根因是 `printer_id` 原为只读 compute 字段，优先读配置表并 `continue` 跳过 `user.zpl_printer_id`，打印后又被写回该表形成闭环。现改为 `printer_id` 可编辑 + `default_get` 直接取 `user.zpl_printer_id`，配置表只用于记住模板。另注意个人资料有两个打印机字段：必须改「ZPL Label Printing」分组的 `zpl_printer_id`，`printing_printer_id`（Printing 分组）本模块不读。
- **本机依赖坑**：`base_report_to_printer` 需要 `pycups`，17.0 venv 原先没装，安装会报 `DistributionNotFound: pycups`；已用 `venv/bin/pip install pycups` 补上。
- **manifest 描述与代码不符**：`__manifest__.py` 的 description 写了「ZPL label printing for Stock Move Lines」，但当前代码**只支持 `repair.order` 模板**（`action_print_labels` 里其它 model 直接抛 `UserError`）。`i18n/zh_CN.po` 里也残留 `move_line_ids` 字段、`stock.move.line` 相关提示的翻译条目（如「使用 stock.move.line 模板时…」「已成功打印…库存移动行」），这些字段/文案在现有 Python 代码中已不存在——属于历史重构遗留。新增/清理翻译时以代码为准，不要照着旧 `.po` 补字段。
- **`copies_per_label` 无取值范围校验**：兄弟 MRP 向导有 `@api.constrains` 限制 1–6；本模块没有，传入 0 会打出 0 张（静默无提示）、传入过大值会逐张循环导致大量打印任务。可考虑加同样的约束。
- **异常被吞成通用 `UserError`**：原始数据访问/网络错误只进日志，前端只看到 `Label printing failed: ...`。排查必须结合日志。
- **Odoo 17 语法**：视图/模型遵循 v17 约定——不要用 v18+ 的 `<list>`、`aggregator=`、`SQL` 类、`models.Constraint`；字符串翻译统一用 `_()`；Python 文件保留 `# -*- coding: utf-8 -*-` 头。
- **`addons_path` 已配置**：`17.0/config/odoo.conf` 的 `addons_path` 已加入 `addons/report-print-send`（2026-11-24；原配置只有 `src/odoo/addons` 和 `addons/odoo-sale-plus`），配置备份在 `config/odoo.conf.bak-20261124`。

---

## 7. 常用操作

### 环境
| 项 | 值 |
|---|---|
| 项目根目录 | `/run/media/max/DATA1/projects/odoo-dev/17.0` |
| 配置文件 | `config/odoo.conf`（HTTP `8017`，gevent `80172`，DB `ot_17.0_111366`，用户 `max`） |
| Python | `17.0/venv/bin/python` |
| 日志 | `17.0/logs/odoo.log` |
| 仓库 | `17.0/addons/report-print-send`（独立 git 仓库，分支 `17.0`） |

### 安装 / 升级
```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0

# 首次安装（config 已带 report-print-send，依赖会自动安装）
unset PYTHONPATH BASH_ENV NODE_OPTIONS PYTHONDONTWRITEBYTECODE
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -i repair_order_zpl_label_print --stop-after-init --http-port=0 --gevent-port=0 --log-level=info

# 改代码后升级
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -u repair_order_zpl_label_print --stop-after-init --http-port=0 --gevent-port=0 --log-level=info
```

启动服务：`venv/bin/python src/odoo/odoo-bin -c config/odoo.conf`（HTTP 8017）。
2026-11-24 已按此流程安装到 `ot_17.0_111366`，服务正常响应 `http://127.0.0.1:8017/web/login`。

### 验证
```bash
# Python 语法
venv/bin/python -m py_compile repair_order_zpl_label_print/models/repair_order.py \
  repair_order_zpl_label_print/wizards/print_repair_zpl_label_wizard.py

# XML 结构
venv/bin/python - <<'PY'
import xml.etree.ElementTree as ET
base = 'addons/report-print-send/repair_order_zpl_label_print/'
for f in ['views/repair_order_views.xml', 'wizards/print_repair_zpl_label_wizard_views.xml']:
    ET.parse(base + f); print(f, 'OK')
PY

# 无需起 HTTP 服务，用 shell 验证模型/方法可用
venv/bin/python src/odoo/odoo-bin shell -c config/odoo.conf -d ot_17.0_111366 --no-http
# >>> print(env['print.repair.zpl.label.wizard'])
# >>> print('config model:', 'printing.label.zpl2.configuration' in env)   # 应为 True
```

### 手工功能验证路径
1. 准备一个 `repair.order` 模型的 `printing.label.zpl2` 模板（含字段组件）。
2. 给当前用户设置 `zpl_printer_id`（用户偏好 → ZPL Label Printer），或在 `printing.label.zpl2.configuration` 里配「用户+模板→打印机」。
3. 打开一张维修单 → 点「Print ZPL Labels」（需 `stock.group_production_lot` 组）→ 检查模板/打印机默认值、份数计算、打印结果与通知。
4. 查 `17.0/logs/odoo.log` 确认无 `ZPL label printing failed` 记录。

---

## 8. 协作约定

- 分支 `17.0`；提交信息用中文 + Conventional 前缀（如 `fix(repair_order_zpl_label_print): ...`）。**未经明确要求不要提交/推送**。
- 改动保持最小、可验证；不要顺手重构兄弟的 `mrp_zpl_label_print` / `stock_picking_zpl_label_print`。
- 若修复 §5 隐藏依赖或 §6 的 manifest/翻译不一致，请同步更新本文件对应章节。
