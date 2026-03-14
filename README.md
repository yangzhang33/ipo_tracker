# IPO Tracker

一个面向个人使用的美国 IPO 数据跟踪系统。

## 安装

### 1. 创建虚拟环境（推荐使用 conda）

```bash
conda create -n ipo_tracker python=3.11
conda activate ipo_tracker
```

或使用 venv：

```bash
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

这将创建：

- `data/ipo_tracker.db`：SQLite 数据库（含全部 5 张表）
- `data/raw/`：原始数据缓存目录
- `data/exports/`：CSV 导出目录

> **升级提示**：如果从旧版升级，建议先删除旧数据库再重新初始化：
>
> ```bash
> rm data/ipo_tracker.db
> python scripts/init_db.py
> ```

## 快速开始：每日全流程

```bash
conda activate ipo_tracker
python scripts/run_daily.py
```

脚本依次执行 5 个步骤，每步打印开始/结束日志，最后输出汇总。
单步失败不会中断后续步骤。

## 数据库表结构

| 表名 | 说明 |
|------|------|
| `issuers` | IPO 候选公司基本信息 |
| `filings` | SEC 提交文件记录 |
| `offerings` | 发行数据（定价、份额等） |
| `capitalization` | 资本化数据（流通股、浮动比率等） |
| `lockups` | 锁定期数据 |

## 项目结构

```text
ipo_tracker/
├── app/
│   ├── config.py          # 配置（路径、数据库 URL、日志级别）
│   ├── db.py              # SQLAlchemy engine / SessionLocal / Base
│   ├── models.py          # 全部 SQLAlchemy 模型（5 张表）
│   ├── schemas.py         # Pydantic 读写 schema
│   ├── collectors/        # Nasdaq / NYSE / SEC 采集器
│   ├── parsers/           # filing 选择、prospectus / lockup 解析
│   ├── jobs/              # 各阶段 job 函数
│   └── utils/             # HTTP / 文本 / 日期 / 日志工具
├── data/
│   ├── raw/               # 原始数据缓存
│   └── exports/           # 导出的 CSV 文件
├── scripts/
│   ├── init_db.py         # 数据库初始化脚本
│   └── run_daily.py       # 每日全流程入口
├── tests/
├── CHANGELOG.md
└── requirements.txt
```

## 手动填入 CIK（SEC filings 同步的前提）

`sync_sec_filings` 只处理 `issuers` 表中已有 `cik` 的公司。
用以下方式查询 CIK，再手动更新数据库：

```python
from app.collectors.sec import search_edgar_company
for hit in search_edgar_company("Reddit"):
    print(hit)
# {"cik": "0001713445", "name": "Reddit, Inc.", "ticker": "RDDT", "exchange": "NYSE"}
```

```sql
UPDATE issuers SET cik = '1713445' WHERE ticker = 'RDDT';
```

## 单独运行各 Job

| Job | 命令 |
|-----|------|
| 发现 IPO 候选 | `python -m app.jobs.discover_candidates` |
| 同步 SEC filings | `python -m app.jobs.sync_sec_filings` |
| 解析发行数据 | `python -m app.jobs.parse_offering_data` |
| 解析 Lock-up | `python -m app.jobs.parse_lockups` |
| 导出 CSV 报表 | `python -m app.jobs.export_reports` |

强制重新解析（覆盖已有记录）：

```bash
python -m app.jobs.parse_offering_data --force
python -m app.jobs.parse_lockups --force
```

## CSV 导出文件

文件写入 `data/exports/`：

| 文件 | 内容 | 筛选条件 |
|------|------|----------|
| `upcoming_ipos.csv` | 即将上市的 IPO | status in (candidate/filed/priced) 且 60 天内有 filing |
| `recent_ipos.csv` | 近期已定价的 IPO | pricing_date 在过去 30 天内 |
| `upcoming_unlocks.csv` | 即将到期的锁定期 | lockup_end_date 在未来 30 天内 |

## 当前进度

- [x] 第一阶段：项目骨架、配置、日志、数据库连接
- [x] 第二阶段：完整数据库模型层（5 张表 + Pydantic schemas）
- [x] 第三阶段：HTTP 工具层（缓存、重试、限速）
- [x] 第四阶段：SEC EDGAR 数据采集函数
- [x] 第五阶段：Nasdaq + NYSE 候选发现 job
- [x] 第六阶段：SEC filings 同步 job
- [x] 第七阶段：最佳 filing 选择器
- [x] 第八阶段：Prospectus 字段解析（offering + capitalization）
- [x] 第九阶段：Lock-up 解析（lockup_days、日期、staged unlock 检测）
- [x] 第十阶段：CSV 导出报表（3 个 CSV 文件）
- [x] 第十一阶段：每日总入口脚本（`scripts/run_daily.py`）
