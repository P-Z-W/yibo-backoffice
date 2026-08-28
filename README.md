# 毅播云仓后台（新系统 V1.0）

老系统成熟业务已迁入现代化架构，新旧系统完全隔离，可同时运行。

## 系统地址与边界

| 系统 | 源码 | 数据库 | 登录地址 |
| --- | --- | --- | --- |
| 新系统 V1.0 | `E:\Projects\yibo-backoffice` | `yibo_backoffice` | <http://127.0.0.1:5000> |
| 老系统稳定备份 | `E:\Projects\yibo-backoffice-old` | `yibo_backoffice_old` | <http://127.0.0.1:5001> |

新系统不会读写老系统本地数据库和业务文件。老系统可继续独立运行成熟业务，作为迁移期间的稳定备份。

## 已迁移范围

- 快递对账：看板、上传运行、历史归档、统计分析、客户/承运商/价格/运行配置及原四步计算核心。
- 数据查询：查询配置、只读 SQL 导出、运行日志、历史文件下载。
- 员工工资：按月查询、增删改、汇总和 Excel 导出。
- 报销管理：快速逐行录入、Excel 批量分组导入、附件上传、主管审批、可选财务审批、审批表批量导出及导出批次追踪。
- 账号与权限：账号启停、默认密码提醒、多岗位角色、权限合并、数据范围和操作审计。
- 经营分析：月度总表与 8 个业务分表、Excel 预览导入、自动汇总、数据完成度与来源追溯、结构化复盘，以及“编辑中—已完成—已归档”的轻量月份状态。
- 历史文件：原 `data`、`output`、公开配置和私有 SQL 配置已复制到新系统独立存储。
- 原系统中尚无成熟功能的财务、仓储入口，在新系统保留同等扩展位置。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、ECharts、Pinia、Vue Router
- 后端：FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、PyMySQL、Pandas
- 数据库：MySQL，字符集 `utf8mb4`
- 认证：同源 Session Cookie、Argon2 密码哈希

## 一键启动

双击根目录 `start-new.bat`。脚本会先升级数据库结构，再启动：

- 新前端：<http://127.0.0.1:5000>
- 新后端：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/api/v1/docs>

员工使用姓名和密码登录，姓名不可重复。管理员也可以继续使用兼容账号 `admin` 登录。密码和数据库连接只保存在本地 `backend/.env`，不会提交 Git。

新建账号和管理员重置密码后，默认密码均为 `423766`。员工首次登录可正常使用系统；后续登录若仍未修改默认密码，系统会提示“立即修改”或“暂时跳过”，跳过后可正常使用并在下次登录继续提醒。新密码最低 6 位，不限制字符组合。

整个系统管理模块仅系统管理员可见、可访问。账号列表中的最新密码使用应用密钥加密保存，仅系统管理员接口会解密返回；历史密码在首次登录、重置或修改后开始记录。

## 从老系统重新执行初始迁移

仅在全新数据库或需要重新构建迁移副本时，双击 `migrate-from-old.bat`。脚本依次升级表结构、复制旧库业务配置和本地文件、导入已确认的经营分析快照。迁移逻辑可重复执行，但会以老系统源数据重新同步对应基础配置。

## 检查命令

```powershell
cd E:\Projects\yibo-backoffice\backend
.\.venv\Scripts\python.exe -m ruff check app scripts tests
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm.cmd test
npm.cmd run build
```

运行期业务文件位于 `backend/storage`，数据库密码位于 `backend/.env`，两者均被 Git 忽略。
