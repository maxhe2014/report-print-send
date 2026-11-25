# ZPL II 标签打印基础模块（printer_zpl2 / 17.0）

## 1. 模块定位

`printer_zpl2` 是 17.0 下所有 ZPL 标签能力的基础模块，负责「标签模板长什么样、生成什么 ZPL 指令、怎么发给打印机」。

它提供：

- 标签模板 `printing.label.zpl2` 与组件 `printing.label.zpl2.component` 数据模型
- ZPL II 指令生成器 `models/zpl2.py`（文本、条码、图形、条码块、重复、子标签）
- 打印入口 `print_label(printer, record, page_count, **extra)`（打印机由调用方显式传入）
- 通用打印向导 `wizard.print.record.label`
- ZPL 文件导入向导 `wizard.import.zpl2`
- Labelary 在线预览与「打印测试标签」

它**不负责**：

- 什么时候打印（业务模型/自动打印触发）
- 用哪台打印机（打印机优先级解析属于消费方模块，如 mrp / stock_picking / repair 的 `*_zpl_label_print`）

当前版本：`17.0.1.2.0`。

## 2. 依赖与运行

```python
"depends": ["base_report_to_printer"]
```

17.0 中 CUPS 打印能力就在 `base_report_to_printer`；19.0 已拆分为 `base_report_to_printer_cups`，向上移植时注意改名。

本地库与配置：

- 配置：`17.0/config/odoo.conf`（库名 `ot_17.0_111366`）
- Python：`17.0/venv/bin/python`
- 启动器：`17.0/src/odoo/odoo-bin`

升级（模块已安装，改代码后用）：

```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -u printer_zpl2 --stop-after-init --log-level=info
```

跑本模块测试：

```bash
cd /run/media/max/DATA1/projects/odoo-dev/17.0
venv/bin/python src/odoo/odoo-bin -c config/odoo.conf -d ot_17.0_111366 \
  -u printer_zpl2 --test-enable --test-tags /printer_zpl2 --stop-after-init
```

> ⚠️ 升级时**只升 `printer_zpl2`**。`printer_zpl2_wizard_enhanced` 的源码 manifest 版本与数据库历史版本可能不一致，连带升级会把向导逻辑换成工作区里的旧版本。确认两者版本一致后再升它。

## 3. 文件地图

| 文件 | 作用 |
|---|---|
| `models/zpl2.py` | ZPL II 指令生成器：常量、字体、条码、图形、块文本截断 |
| `models/printing_label_zpl2.py` | 标签模板模型：字段、ZPL 数据生成、打印入口、Action 绑定、Labelary 预览 |
| `models/printing_label_zpl2_component.py` | 组件模型：类型、位置、格式、数据自动填充 |
| `models/printing_label_zpl2_user_action.py` | 每用户每标签的打印机覆盖记录（本次从 19.0 移植） |
| `wizard/print_record_label.py` | 通用打印向导：打印机/标签选择、打印 |
| `wizard/wizard_import_zpl2.py` | 导入 `.zpl` 文件，解析为模板组件 |
| `views/printing_label_zpl2.xml` | 标签模板列表/表单/搜索、用户打印机页、菜单与 Action |
| `security/ir.model.access.csv` | 打印用户/管理员的 ACL |
| `tests/` | 模板生成、向导、导入、测试模式、Action 生成 |
| `readme/` | OCA 说明片段（DESCRIPTION / CONFIGURE / USAGE / INSTALL / HISTORY） |

## 4. 数据模型

### 4.1 标签模板 `printing.label.zpl2`

| 字段 | 说明 |
|---|---|
| `name` / `active` / `description` | 基本信息 |
| `model_id` | 该模板适用的业务模型（`ir.model`） |
| `origin_x` / `origin_y` / `width` | 标签原点与宽度 |
| `darkness` | 打印浓度 `^MD`，-30 ~ 30，0 为默认 |
| `component_ids` | 组件列表，复制时一并复制 |
| `restore_saved_config` | 每个标签结束后恢复打印机保存的配置 |
| `action_window_id` | 「Add in the 'Action' menu」绑定出的动作 |
| `test_print_mode` / `test_labelary_mode` | 测试打印 / Labelary 预览开关 |
| `record_id` / `extra` | 测试打印用的记录与额外 eval 变量 |
| `printer_id` | **仅用于「打印测试标签」**，不参与自动打印分配 |
| `default_printer_id` | 该模板的默认打印机（数据/界面层，解析在消费方） |
| `user_action_ids` | 每用户打印机覆盖（数据/界面层，解析在消费方） |
| `labelary_*` | Labelary 预览的密度、宽高 |

关键方法：

- `_generate_zpl2_data(record, page_count=1, **extra)`：生成整张标签的 ZPL
- `print_label(printer, record, page_count=1, **extra)`：把 ZPL 发给显式传入的打印机
- `add_action` / `create_action` / `unlink_action`：绑定/解绑模型菜单动作
- `print_test_label` / `_generate_labelary_image`：测试打印与预览

### 4.2 组件 `printing.label.zpl2.component`

组件类型：

`text`、`rectangle`、`diagonal`、`circle`、`graphic`、各类条码（Code 11 / ITF / Code 39 / Code 49 / PDF417 / EAN-8 / UPC-E / Code 128 / EAN-13）、`qr_code`、`qr_code_custom`、`datamatrix`、`sublabel`、`zpl2_raw`。

主要能力：

- 位置、尺寸、旋转、反色、重复打印（`repeat*`）
- 文本块 `in_block`：`block_width/lines/spaces/justify/left_margin`
- 自定义字体：`font = "@"` + `custom_font_name`，生成 `^A@N,h,w,字体名`
- 数据自动填充 `data_autofill` + `autofill_data()`（Python 表达式 safe_eval）
- 子标签 `sublabel_id`（可递归，模板上有环检测）

17.0 相对 19.0 多出的能力（**19.0 没有，需保留**）：

- **Data Matrix**：`quality` / `columns` / `rows` / `format_type` / `escape_sequence` / `additional_info`，生成 8 参数 `^BX...`
  - 注意：这些 DM 参数字段目前**没有暴露在视图**里，只能用默认值或代码写入
- **QR Code (Custom)**：`qr_code_custom`，复用 QR 生成器，但 `data_autofill=False`（手动填数据）
- **文本块自动截断**：`zpl2._truncate_block_text()`，按中英文宽度估算截断并追加 `...`

### 4.3 用户打印机覆盖 `printing.label.zpl2.user.action`

| 字段 | 说明 |
|---|---|
| `label_id` | 标签模板，级联删除 |
| `user_id` | 用户，级联删除 |
| `printer_id` | 该用户打印该标签时使用的打印机（可空） |
| `active` | 关掉即失效，回落到标签默认/用户默认 |

约束：`unique(label_id, user_id)`（17.0 用 `_sql_constraints`，19.0 用 `models.Constraint`）。

> 该模型只存数据与界面。真正「用户级 > 标签默认 > 用户默认」的解析逻辑在自动打印消费方模块里实现，不在本模块。

## 5. ZPL 生成流程

```
_generate_zpl2_data(record, page_count, **extra)
  ├─ 标签头：^XA / ^PW宽度 / ^CI28 / ^LH原点
  ├─ 可选：^MD浓度
  ├─ 遍历 component_ids → _generate_zpl2_components_data()
  │    ├─ text        → font_data()（含块格式、截断、自定义字体）
  │    ├─ 条码        → barcode_data() → ^B... + ^FD
  │    ├─ qr_code     → ^BQ + error_correction 前缀
  │    ├─ datamatrix  → ^BX(8 参数)
  │    ├─ graphic     → ^GF 位图
  │    ├─ rectangle/diagonal/circle → ^GB / ^GC
  │    ├─ sublabel    → 递归渲染子标签
  │    └─ zpl2_raw    → 原样输出
  └─ 标签尾：^JUR（按配置）/ ^XZ
```

`safe_eval` 可见变量：`object`（当前记录）、`page_number`、`page_count`、`time`、`datetime`、`date`、`context` 等。17.0 **额外暴露 `env`**，19.0 已移除（安全收紧）。

## 6. 通用打印向导 `wizard.print.record.label`

| 字段 | 说明 |
|---|---|
| `printer_id` | 必填，打印机 |
| `label_id` | 必填，域为 `[('model_id', '=', active_model_id)]`（本次从 19.0 移植） |
| `active_model_id` | 目标模型，Action 通过 `default_active_model_id` 带入 |
| `model` | related `active_model_id.model` |
| `line_ids` | 历史残留，未进视图、打印逻辑不读取 |

`default_get()`：

- 没有指定 `printer_zpl2_id` 时搜索打印机，`limit=2`（本次从 19.0 移植，仅用于判断「是否唯一」）
- 只有一台打印机时自动带出
- 只有一张匹配标签时自动带出

`print_label()`：按 `active_ids` 逐条调用 `label.print_label(printer, record)`。

> 本库装了 `printer_zpl2_wizard_enhanced`，它在 Python 与视图里都重写了 `label_id` 域（`action_window_id != False` + 按 `model` 过滤）并接管了数量策略与打印。所以基础模块的域改动在本库被覆盖，属预期。

## 7. 安全

`security/ir.model.access.csv` 使用 `base_report_to_printer` 的两个组：

- `printing_group_user`：模板/组件只读；用户打印机覆盖只读；向导可读写
- `printing_group_manager`：全部读写

## 8. 已知约束与坑

1. **打印机解析不在本模块**：`print_label` 永远使用调用方传入的打印机；`default_printer_id` / `user_action_ids` 目前是数据+界面。移植自动打印消费方模块时，再统一实现「用户级 > 标签默认 > 用户默认 > 报错」。
2. **不要照搬 19.0 的视图改名**：19.0 把 `view_printing_label_zpl2_tree` 改成 `_list`、`tree` 改 `list`。17.0 保持原 id，其他模块（含增强向导）依赖它们。
3. **不要带上 19.0 视图的 `invisble` 拼写错误**（应为 `invisible`）。
4. **数据安全**：现网标签模板多为手工创建，不在 `ir_model_data` 中，模块升级不会覆盖或删除；新增字段均为可空/新表，无数据迁移。
5. **打印浓度**：`darkness` 生成 `^MD`，仅非 0 时写入。
6. **Data Matrix 参数未进视图**：如需在界面配置，要补视图页。
7. **Labelary 预览依赖外网**；`tests/test_test_mode.py` 通过 patch `requests.post` 避免真实请求。

## 9. 与 19.0 的差异（移植参考）

17.0 已有、19.0 缺失：

- Data Matrix 条码与 6 个参数字段
- QR Code (Custom)
- 文本块自动截断 `_truncate_block_text`
- `safe_eval` 暴露 `env`

19.0 已有、本次已移植到 17.0：

- `default_printer_id` + `user_action_ids` + `printing.label.zpl2.user.action` + ACL + 视图页
- 向导 label 域改为按 `active_model_id`
- 向导打印机搜索 `limit=2`

19.0 有但**未移植**：

- `product_template_views.xml`（空的 invisible 占位页；17.0 的产品标签字段由 `mrp_zpl_label_print` 提供）
- `models.Constraint` / `tree→list` / `self.env._` 等 19.0 平台写法

## 10. 变更记录

- `17.0.1.2.0`：从 19.0 移植用户级打印机分配（数据+界面）、向导 label 域修复、打印机搜索 `limit=2`。升级后已验证：6 条模板、6 个组件、产品 `车架(id=86)→模板 32` 均保持不变；模块测试 47 项全通过。
- `17.0.1.1.0`：支持 `^MD` 打印浓度。
