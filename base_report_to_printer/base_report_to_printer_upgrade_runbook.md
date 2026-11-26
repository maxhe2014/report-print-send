# base_report_to_printer 生产环境升级手册（托盘字段迁移）

> 适用场景：Docker Compose 部署的 Odoo 17，升级 `base_report_to_printer` 到 `17.0.1.2.6` 时，因容器内缺少 `openupgradelib` 导致上游迁移脚本（`17.0.1.1.2/pre-migration.py`）执行失败，系统报 `UndefinedColumn: column res_users.printer_input_tray_id does not exist` 无法登录。

---

## 一、问题现象

升级后访问 Odoo 首页报错：

```
UndefinedColumn: column res_users.printer_input_tray_id does not exist
Template: website.layout
Node: <t t-set="info" t-value="website._get_livechat_channel_info()"/>
```

根因：上游迁移脚本依赖 `openupgradelib`，Docker 镜像未安装该库，迁移未执行；但代码已更新到新版，引用了不存在的新字段名。

---

## 二、前置条件

- 服务器有 `docker-compose` 权限（项目目录默认 `/home/docker/odoo17e-2`）
- 数据库容器名：`odoo17e-2-db-1`，应用容器名：`odoo17e-2-web-1`
- 数据库名：`V1.1`（如不同请替换）
- 已备份数据库（执行前强烈建议先 `pg_dump`）

```bash
# 备份
docker exec odoo17e-2-db-1 pg_dump -U odoo V1.1 > ~/V1.1_backup_$(date +%Y%m%d).sql
```

---

## 三、执行步骤

### 步骤 1：进入数据库容器

```bash
docker exec -it odoo17e-2-db-1 psql -U odoo -d V1.1
```

### 步骤 2：手动完成模型/字段元数据迁移

在 psql 中依次执行（每条单独一行）：

```sql
-- 2.1 重命名模型 printing.tray -> printing.tray.input
UPDATE ir_model SET model = 'printing.tray.input' WHERE model = 'printing.tray';

-- 2.2 更新 ir_model_data 外部 ID（如已改过会返回 UPDATE 0，正常）
UPDATE ir_model_data SET name = 'model_printing_tray_input'
WHERE name = 'model_printing_tray' AND model = 'ir.model';

-- 2.3 重命名字段元数据（3 个表：res_users / ir_act_report_xml / printing_report_xml_action）
UPDATE ir_model_fields SET name = 'printer_input_tray_id' WHERE name = 'printer_tray_id';
```

### 步骤 3：修正物理列名

```sql
-- 3.1 ir_act_report_xml 物理列改名（注意表名是 ir_act_report_xml，不是 ir_actions_report）
ALTER TABLE ir_act_report_xml RENAME COLUMN printer_tray_id TO printer_input_tray_id;

-- 3.2 验证：3 行结果都应该是 printer_input_tray_id
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name LIKE '%tray%'
AND table_name IN ('res_users', 'ir_act_report_xml', 'printing_report_xml_action');
```

预期输出：

```
         table_name         |      column_name
----------------------------+-----------------------
 ir_act_report_xml          | printer_input_tray_id
 printing_report_xml_action | printer_input_tray_id
 res_users                  | printer_input_tray_id
(3 rows)
```

> 如果某条 ALTER 报 `column "printer_tray_id" does not exist`，说明之前已改过，跳过即可，不影响。

### 步骤 4：标记模块为待升级状态（让 Odoo 正常加载新代码建新表）

```sql
-- 4.1 版本标记设为最新（跳过依赖 openupgradelib 的迁移脚本）
UPDATE ir_module_module SET latest_version = '17.0.1.2.6' WHERE name = 'base_report_to_printer';

-- 4.2 标记为 to upgrade，让 Odoo 启动时自动重建新表/新列
UPDATE ir_module_module SET state = 'to upgrade' WHERE name = 'base_report_to_printer';

-- 4.3 退出
\q
exit
```

### 步骤 5：重启 web 容器

```bash
cd /home/docker/odoo17e-2
docker-compose restart web

# 等待 Odoo 完成模块升级（通常需要 30~90 秒）
sleep 60
```

---

## 四、验证

### 4.1 检查新表已自动创建

```bash
docker exec -it odoo17e-2-db-1 psql -U odoo -d V1.1
```

```sql
-- 应该看到 printing_tray_input 和 printing_tray_output 两张表
\dt printing_tray*

-- 应该看到 input + output 两类列（共 6 行左右）
SELECT table_name, column_name FROM information_schema.columns
WHERE column_name LIKE '%tray%';
```

### 4.2 浏览器验证

访问 `https://<你的域名>/web/login`，能正常打开登录页并登录即修复完成。

### 4.3 应用日志（过滤噪音）

```bash
cd /home/docker/odoo17e-2
docker-compose logs web --tail=200 2>&1 | grep -viE "collation|version mismatch|REBUILD|run ALTER" | tail -30
```

---

## 五、一次性执行脚本（可直接复制）

```bash
# ==== 在服务器上一次性执行 ====

# 1. 备份
docker exec odoo17e-2-db-1 pg_dump -U odoo V1.1 > ~/V1.1_backup_$(date +%Y%m%d).sql

# 2. 执行 SQL 迁移
docker exec -i odoo17e-2-db-1 psql -U odoo -d V1.1 <<'SQL'
UPDATE ir_model SET model = 'printing.tray.input' WHERE model = 'printing.tray';
UPDATE ir_model_data SET name = 'model_printing_tray_input'
  WHERE name = 'model_printing_tray' AND model = 'ir.model';
UPDATE ir_model_fields SET name = 'printer_input_tray_id' WHERE name = 'printer_tray_id';
ALTER TABLE ir_act_report_xml RENAME COLUMN printer_tray_id TO printer_input_tray_id;
UPDATE ir_module_module SET latest_version = '17.0.1.2.6' WHERE name = 'base_report_to_printer';
UPDATE ir_module_module SET state = 'to upgrade' WHERE name = 'base_report_to_printer';
SQL

# 3. 重启并等待
cd /home/docker/odoo17e-2
docker-compose restart web
sleep 60

# 4. 验证
docker exec odoo17e-2-db-1 psql -U odoo -d V1.1 -c "\dt printing_tray*"
curl -s -o /dev/null -w "HTTP=%{http_code}\n" http://localhost:8069/web/login
```

---

## 六、长期建议（避免再次发生）

1. **在 Docker 镜像中预装 `openupgradelib`**：在 Dockerfile 里加 `RUN pip install openupgradelib`，以后上游迁移脚本能自动执行，无需手动 SQL。
2. **升级前先在测试环境验证**，确认迁移脚本跑通后再上生产。
3. **忽略 collation 警告**（`database "postgres" has a collation version mismatch`）：这是 PostgreSQL 大版本升级后的无害提示，不影响 Odoo 运行，可执行 `ALTER DATABASE postgres REFRESH COLLATION VERSION;` 消除。

---

## 七、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 重启后仍报 `printer_output_tray_id does not exist` | 模块没真正重新加载 | 重复步骤 4.2 + 重启 |
| `relation "ir_actions_report" does not exist` | 表名写错 | 正确表名是 `ir_act_report_xml` |
| Odoo 一直起不来 | 还有其他缺列/缺表 | 看 `docker-compose logs web` 过滤后的报错，逐个补列 |
| 想完全回退 | 用 `pg_dump` 备份恢复 | `docker exec -i odoo17e-2-db-1 psql -U odoo -d V1.1 < ~/V1.1_backup_YYYYMMDD.sql` |
