# 📒 记账日历

本地记账日历系统 — FastAPI + SQLite + 原生 HTML 单文件前端。

## 功能一览

| 功能 | 说明 |
|------|------|
| 📅 月历视图 | 按日展示收支，130px 大格子，周末标红，今天高亮 |
| ➕ 记账 | 支出/收入切换，支持分类、项目、备注，支持复制粘贴带逗号的金额 |
| 📊 统计 | 按月汇总（收入/支出/结余），右上角实时显示 |
| 🔔 还款提醒 | 设置每月固定还款，支持起止月份、金额、总欠款、颜色标记 |
| 🏦 本月待还款 | 日历下方卡片展示当月所有待还，可逐条勾选完成 |
| 💰 总待还统计 | 右上角显示所有未完成还款的累计金额（有总欠款按总欠款算，无则按月供×剩余月数） |
| 💾 备份恢复 | 启动时自动备份（仅数据有变化时），支持手动备份和一键恢复 |
| 🌙 深色模式 | 一键切换深色/浅色主题，偏好记忆在 localStorage |
| 📱 响应式 | 700px 以下自动适配移动端布局 |
| 🔑 键盘快捷键 | Esc 关闭弹窗/面板，← → 切换月份 |

## 快速启动

```bash
cd "项目目录"
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

浏览器访问 http://localhost:8000

## 项目结构

```
├── main.py              # FastAPI 主应用（路由 + 前端托管）
├── database.py          # SQLite 初始化、迁移、备份
├── schemas.py           # Pydantic 请求/响应模型
├── parser.py            # 自然语言解析（Ollama + 正则 fallback）
├── index.html           # 前端（月历 + 深色模式，单文件）
├── requirements.txt     # Python 依赖
├── launcher.py          # 桌面版启动入口
├── build_onefile.bat    # 打包脚本
├── run_desktop_dev.bat  # 桌面版开发调试启动
├── open_data_folder.bat # 打开数据目录
└── FinanceCalendar.spec # PyInstaller 配置
```

## API 接口

### 交易记录

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/transactions` | 查询（支持 `start_date` `end_date` `type` `category_id` `project_id`） |
| POST | `/transactions` | 新增 |
| GET | `/transactions/{id}` | 查看单笔 |
| PUT | `/transactions/{id}` | 编辑 |
| DELETE | `/transactions/{id}` | 删除 |

### 还款提醒

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/reminders` | 列出所有提醒 |
| POST | `/reminders` | 新增（支持 `amount` 最低还款、`total_debt` 总欠款） |
| PUT | `/reminders/{id}` | 编辑 |
| DELETE | `/reminders/{id}` | 删除 |
| POST | `/reminders/{id}/done` | 标记某月已还 |
| DELETE | `/reminders/{id}/done?year_month=` | 取消标记 |
| GET | `/reminders/status?year_month=` | 获取指定月份还款状态 |
| GET | `/reminders/future-total` | 所有未还月份的累计待还总额 |

### 分类 & 项目

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/categories` | 列出 / 新增 |
| PUT/DELETE | `/categories/{id}` | 编辑 / 删除 |
| GET/POST | `/projects` | 列出 / 新增 |
| PUT/DELETE | `/projects/{id}` | 编辑 / 删除 |

### 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stats/monthly` | 按月汇总（`year` 参数） |
| GET | `/stats/category` | 按分类统计 |
| GET | `/stats/project` | 按项目统计 |

### 备份

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/backups` | 列出所有备份 |
| POST | `/backups` | 手动创建备份 |
| POST | `/backups/restore?filename=` | 从备份恢复 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 前端页面 |
| GET | `/health` | 健康检查 |

## 默认分类

**支出：** 餐饮、交通、购物、娱乐、居住、医疗、教育、通讯、其他支出

**还款：** 信用卡还款、花呗还款、贷款还款、其他还款

**收入：** 工资、奖金、投资、兼职、其他收入

## 技术栈

- **后端：** Python + FastAPI + SQLite + Uvicorn
- **前端：** 原生 HTML/CSS/JS 单文件，Apple 风格设计
- **数据：** SQLite WAL 模式，启动时自动备份
