# Changelog

## [Step 8] - 2026-03-14 — Prospectus 字段解析

### 新增文件

#### `app/parsers/prospectus_parser.py`

共用辅助函数：
- **`_first(patterns, text, group)`** — 遍历 pattern 列表取第一个匹配，None-safe
- **`_parse_number(raw)`** — 处理逗号/小数/million/billion 后缀，返回 float 或 None

主要解析函数（均接受 `strip_html_to_text()` 输出的纯文本）：

| 函数 | 目标字段 | 典型句式 |
|------|----------|----------|
| `extract_offer_price` | offer_price | "offering price per share ... is $34.00" |
| `extract_price_range` | price_low, price_high | "$25.00 to $31.50 per share" |
| `extract_shares_offered_total` | shares_offered_total | "Company Inc. is offering 15,276,527 shares of its..." |
| `extract_shares_primary_secondary` | shares_primary, shares_secondary | "Company is offering X shares... selling stockholders are offering Y shares" |
| `extract_greenshoe_shares` | greenshoe_shares | "X shares ... to cover over-allotment" / "option to purchase X additional shares" |
| `extract_bookrunners` | bookrunners | cover-page ALL-CAPS block between "deliver the shares" and "Prospectus dated" |

每个函数有 2–4 个 fallback pattern；找不到返回 None，不猜测。

#### `app/parsers/capitalization_parser.py`

| 函数 | 目标字段 | 策略 |
|------|----------|------|
| `extract_shares_outstanding_post_ipo` | shares_outstanding_post_ipo | 优先匹配多 class 合计（最大值）；fallback 取所有"outstanding after offering"中最大数 |
| `extract_shares_outstanding_pre_ipo` | shares_outstanding_pre_ipo | "X shares outstanding as of [date]" 在 offering 前 |
| `extract_fully_diluted_shares` | fully_diluted_shares | "X shares ... on a fully diluted basis" |

#### `app/jobs/parse_offering_data.py`

- **`parse_offering_data(force=False) -> dict`**
  - 对所有 issuer 查询 filings → `select_best_filing` → 下载 HTML → `strip_html_to_text` → 调用 parsers
  - **`shares_offered_total` 计算优先级**：primary + secondary（相加）> 直接提取 > primary 单独值
  - `gross_proceeds` = `offer_price × shares_offered_total`（均不为 None 时自动计算）
  - `float_ratio` = `shares_offered_total / shares_outstanding_post_ipo`（均不为 None 时自动计算）
  - Upsert offerings / capitalization：`_set_if_not_none` — 有解析结果就覆盖，None 不动
  - 解析完成后标记 `filing.is_parsed = 1`
  - `force=True` 强制重新解析已标记的 filing（`--force` CLI flag）
  - 每个 issuer 独立 try/except，失败计入 `failed`
  - 返回 `{issuer_count, parsed, skipped, failed}`
  - 支持 `python -m app.jobs.parse_offering_data [--force]`

#### `tests/test_prospectus_parser.py`

18 个单元测试，覆盖全部解析函数：

- `offer_price`：424B4 句式、price to public、None
- `price_range`：to 连接、between...and、None
- `shares_offered_total`：cover page 句式、None
- `shares_primary_secondary`：公司+selling stockholder 句式
- `greenshoe`：to cover 句式、option to purchase 句式、None
- `bookrunners`：ALL-CAPS cover-page block
- `shares_outstanding_post_ipo`：多 class 合计、简单句式、None
- `shares_outstanding_pre_ipo`：as of date 句式
- `fully_diluted_shares`：fully diluted basis 句式

### 不变文件
- `app/parsers/filing_locator.py` — 无需修改
- `app/collectors/` / `app/jobs/sync_sec_filings.py` — 无需修改
- `app/models.py` / `app/schemas.py` — 无需修改

### 已知限制（v1）
- `shares_outstanding_pre_ipo` 对 Reddit 424B4 返回 None（没有简单 "X shares outstanding as of" 句式）
- `fully_diluted_shares` 对 Reddit 424B4 返回 None（数字在 GAAP 表格中，纯文本解析困难）
- bookrunners 模式依赖 cover-page 结构，非标准 prospectus 格式可能失效

### 验证（Reddit Inc. 424B4 实测）

| 字段 | 期望 | 实测 |
|------|------|------|
| offer_price | 34.0 | ✓ 34.0 |
| shares_offered_total | 22,000,000 | ✓ 22,000,000 |
| shares_primary | 15,276,527 | ✓ 15,276,527 |
| shares_secondary | 6,723,473 | ✓ 6,723,473 |
| greenshoe_shares | 3,300,000 | ✓ 3,300,000 |
| gross_proceeds | 748,000,000 | ✓ 748,000,000 |
| shares_outstanding_post_ipo | 158,993,090 | ✓ 158,993,090 |
| bookrunners | 15 banks | ✓ 15 banks |

---

## [Step 7] - 2026-03-14 — 最佳 Filing 选择器

### 新增文件

#### `app/parsers/filing_locator.py`

- **新增** `select_best_filing(filings: list) -> Any | None`
  - 输入：Filing ORM 对象列表或 dict 列表，空列表返回 None
  - 优先级梯（固定，从高到低）：
    1. `424B4`
    2. `424B1`
    3. `S-1/A` / `F-1/A`（同组）
    4. `S-1` / `F-1`（同组）
  - 同一梯内按 `filing_date` 取最新（字符串 ISO 比较，None 退化为 `""`）
  - 所有 form_type 均不在优先级表中时返回 None
  - **`_get(filing, field)`** 内部辅助：统一读取 dict 和 ORM 对象的字段，使函数与输入类型无关
  - 无外部依赖，纯 Python 标准库

#### `tests/test_filing_locator.py`

10 个测试用例，覆盖规范要求的全部场景：

| 测试 | 验证点 |
|------|--------|
| `test_empty_returns_none` | 空列表 → None |
| `test_only_s1_selects_s1` | 仅 S-1 → 选 S-1 |
| `test_s1a_beats_s1` | 有 S-1/A → 优先 S-1/A |
| `test_424b4_beats_s1a` | 有 424B4 → 优先 424B4 |
| `test_424b4_beats_424b1` | 424B4 > 424B1 |
| `test_latest_date_wins_within_tier` | 同级多个 → 取最新日期 |
| `test_f1_selected_when_no_s1` | F-1 路径正常 |
| `test_f1a_beats_f1` | F-1/A > F-1 |
| `test_unrecognised_forms_return_none` | 无关表单 → None |
| `test_orm_like_object` | ORM 属性对象兼容 |

### 修改文件

#### `requirements.txt`
- 新增 `pytest>=9.0.0`

### 不变文件
- `app/models.py` / `app/schemas.py` / `app/db.py` — 无需修改
- `app/jobs/` — 无需修改
- `app/collectors/` — 无需修改

### 验证

```
pytest tests/test_filing_locator.py -v
10 passed in 0.01s
```

---

## [Step 6] - 2026-03-14 — SEC Filings 同步

### 新增文件

#### `app/jobs/sync_sec_filings.py`

- **新增** `sync_sec_filings(use_cache=True) -> dict`
  - 查询 `issuers` 表中 `cik IS NOT NULL` 的所有公司
  - 对每个 issuer 调用 `get_submissions_json(cik)` + `extract_recent_target_forms()`
  - 按 unique 约束 `(issuer_id, accession_no, form_type)` 判重，新则 INSERT，旧则 skip
  - 每个 issuer 独立 try/except + commit，单个失败不中断其余处理
  - **`_derive_status(current, form_types)`** 内部辅助：
    - `RW` → `"withdrawn"`（最高优先级，始终覆盖）
    - `"priced"` / `"trading"` → 保持不降级
    - S-1 / S-1/A / F-1 / F-1/A / 424B4 / 424B1 → 升为 `"filed"`（若当前为 `"candidate"`）
    - 无相关表单 → 保持现状
  - **`_sync_one_issuer()`** 内部辅助：单 issuer 处理逻辑，含 status 更新和 commit
  - 返回 `{issuer_count, filings_inserted, filings_skipped, filings_failed}`
  - 支持 `python -m app.jobs.sync_sec_filings` 直接运行

### 修改文件

#### `app/collectors/sec.py`
- **新增** `search_edgar_company(query, max_results=10) -> list[dict]`
  - 下载 `https://www.sec.gov/files/company_tickers_exchange.json`（走 HTTP 缓存）
  - 按 ticker 精确匹配或 company name 子串匹配（大小写不敏感）
  - 返回 `{cik, name, ticker, exchange}` 列表
  - 用途：帮助用户手动查找 CIK 后填入 issuers 表

#### `README.md`
- 新增"手动填入 CIK"章节（含 `search_edgar_company` 用法和 SQL 示例）
- 新增"运行 SEC Filings 同步任务"章节
- 更新"当前进度"列表

### 不变文件
- `app/models.py` / `app/schemas.py` — 无需修改（filings 表结构已满足需求）
- `app/jobs/discover_candidates.py` — 无需修改
- `app/utils/` — 无需修改

### 验证
- `search_edgar_company("Reddit")` → `[{"cik": "0001713445", "name": "Reddit, Inc.", ...}]`
- 手动插入 Reddit CIK 后运行 `sync_sec_filings()`：
  - 第一次：inserted=5, skipped=0, failed=0；status `candidate → filed`
  - 第二次（幂等验证）：inserted=0, skipped=5, failed=0

---

## [Step 5] - 2026-03-14 — IPO 候选公司发现

### 新增文件

#### `app/collectors/nasdaq.py`
- **新增** `fetch_nasdaq_candidates(lookback_months, lookahead_months, use_cache) -> list[dict]`
  - 调用 `https://api.nasdaq.com/api/ipo/calendar?date=YYYY-MM`（需要浏览器 User-Agent，不能用 SEC_USER_AGENT）
  - 默认抓取前 1 个月 + 当月 + 后 2 个月，共 4 次请求
  - 合并三个 section：`priced`（pricedDate）、`upcoming.upcomingTable`（expectedPriceDate）、`filed`（filedDate）；排除 `withdrawn`
  - 按 `dealID` 在函数内去重，防止同一 deal 跨月重复
  - 每个候选 dict 字段：`company_name`、`ticker`、`exchange`、`source_url`、`raw_date_text`

#### `app/collectors/nyse.py`
- **新增** `fetch_nyse_candidates(use_cache) -> list[dict]`
  - 调用 `https://www.nyse.com/api/ipo-center/calendar`（通过分析 NYSE IPO Center JS bundle 发现）
  - 排除 `deal_status_flg == "W"`（withdrawn）的 deal
  - epoch ms 时间戳转 ISO 日期（负值、TBA 占位值 > 4102444800000 均返回 None）
  - 数据源字段：`issuer_nm` → `company_name`、`symbol` → `ticker`、`custom_group_exchange_nm` → `exchange`

#### `app/jobs/discover_candidates.py`
- **新增** `discover_candidates() -> dict`
  - 独立调用 Nasdaq / NYSE 两个 collector，单个 source 失败不影响另一个
  - 内存去重 key：`(ticker.upper(), company_name.lower())`，空 company_name 跳过
  - DB upsert 逻辑：
    1. 按 ticker 查找，若无则按 company_name（ilike）查找
    2. 找到：仅当 exchange / ticker / source_url 为空时补填，设 updated_at
    3. 未找到：INSERT，status = "candidate"
  - 返回 `{total_fetched, inserted, updated, skipped}`
- **支持直接运行**：`python -m app.jobs.discover_candidates`（`__main__` 块）

### 修改文件

#### `app/models.py`
- `Issuer` 新增 `source_url = Column(Text, nullable=True)` — 记录候选来源页面 URL
- ⚠️ 需重置数据库：`rm data/ipo_tracker.db && python scripts/init_db.py`

#### `app/schemas.py`
- `IssuerCreate` / `IssuerRead` 新增 `source_url: Optional[str] = None`

#### `README.md`
- 新增"运行 IPO 候选发现任务"章节，含命令行示例和 DB 重置提示
- 更新"当前进度"列表

### 不变文件
- `app/utils/` — 无需修改
- `app/collectors/sec.py` — 无需修改
- `app/db.py` / `app/config.py` — 无需修改

### 验证
- `fetch_nasdaq_candidates()`：抓取 105 条候选（当月前后共 4 个月）
- `fetch_nyse_candidates()`：抓取 13 条候选
- 内存去重后 115 条唯一候选
- `discover_candidates()` 一次运行：inserted=115, updated=0, skipped=0
- 第二次运行（幂等性验证）：inserted=0, updated=0, skipped=115

---

## [Step 4] - 2026-03-13 — SEC 数据采集层

### 新增文件

#### `app/collectors/sec.py`

实现 6 个公开函数，不写数据库、不实现 job/parser，模块完全独立可测试。

- **`get_sec_headers() -> dict`**
  - 返回 SEC EDGAR 专用请求头：`User-Agent`（从 `settings.SEC_USER_AGENT` 读取）、`Accept`、`Accept-Encoding`
  - 调用方可用 `headers` 参数覆盖任意字段

- **`normalize_cik(cik) -> str`**
  - 将任意格式 CIK（字符串或整数）规范为 10 位零填充字符串
  - e.g. `320193` → `"0000320193"`

- **`get_submissions_json(cik, use_cache) -> dict`**
  - 拼接 URL `https://data.sec.gov/submissions/CIK{cik10}.json`
  - 调用 `get_json`（复用 Step 3 缓存 + 重试 + 限速机制）
  - `use_cache=True` 默认开启

- **`build_filing_primary_doc_url(cik, accession_no, primary_doc) -> str`**
  - 构造 `https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_no_dashes}/{primary_doc}`
  - accession_no 去掉连字符用于路径；CIK 取整数形式（去掉前置零）

- **`build_filing_index_url(cik, accession_no) -> str`**（内部辅助，供 `extract_recent_target_forms` 使用）
  - 构造 filing 归档目录 URL

- **`download_filing_html(url, use_cache) -> str`**
  - 调用 `get_text`（复用 Step 3 缓存机制）下载 filing HTML
  - `use_cache=True` 默认开启

- **`extract_recent_target_forms(submissions_json) -> list[dict]`**
  - 从 `filings.recent` 并行数组中提取目标表单
  - 目标类型：`S-1 | S-1/A | F-1 | F-1/A | 424B4 | 424B1 | RW`
  - 每项字段：`accession_no`、`form_type`、`filing_date`、`primary_doc`、`primary_doc_url`、`filing_index_url`
  - 字段缺失容错（`_safe_get` 防止 IndexError）
  - 结果按 `filing_date` 降序排列（最新在前）
  - 仅覆盖 `filings.recent` 块（约最近 1000 条），`filings.files` 留待后续阶段

### 不变文件
- `app/config.py` — 无需修改（`SEC_USER_AGENT` 已在 Step 3 修复中添加）
- `app/utils/` — 无需修改
- `app/models.py` / `app/schemas.py` / `app/db.py` — 无需修改
- `README.md` — 无需修改

### 验证
- `normalize_cik` 单元断言通过
- Apple CIK `320193`：submissions JSON 正常拉取，0 条目标表单（符合预期，Apple 1980 年上市）
- Reddit CIK `1713445`：正确提取 5 条目标表单（S-1 + 3×S-1/A + 424B4，2024 年 IPO）

---

## [Step 3] - 2026-03-11 — 基础工具层

### 新增文件

#### `app/utils/http.py`
- **新增** `get_text(url, headers, use_cache) -> str`
  - 支持超时（`HTTP_TIMEOUT`）、自动重试（tenacity，最多 `HTTP_MAX_RETRIES` 次）
  - 重试条件：`httpx.TimeoutException` / `httpx.NetworkError`；HTTP 4xx/5xx 不重试
  - 重试等待：指数退避，2 ~ 15 秒
  - 支持限速（`HTTP_RATE_LIMIT_DELAY`），模块级时间戳跨调用生效
  - 缓存路径：`data/raw/cache/<sha256前24位>.txt`
- **新增** `get_json(url, headers, use_cache) -> dict`
  - 与 `get_text` 相同的重试/限速/缓存机制
  - 缓存路径：`data/raw/cache/<sha256前24位>.json`，序列化时保留非 ASCII
- **新增** `_fetch(url, headers)` — 内部重试装饰器封装，不暴露给外部；自动注入 `SEC_USER_AGENT` 作为默认 `User-Agent`，调用方传入的 headers 可覆盖

#### `app/utils/text.py`
- **新增** `normalize_whitespace(text) -> str`
  - 将任意连续空白折叠为单个空格，首尾裁剪
- **新增** `strip_html_to_text(html) -> str`
  - 使用 selectolax 解析 HTML，移除 `<script>` / `<style>` / `<head>`
  - 块级元素用换行分隔，保留段落结构
  - 连续 3+ 空行折叠为 2 行
- **新增** `find_section(text, section_titles) -> str | None`
  - 按 section_titles 优先级顺序进行大小写不敏感子串搜索
  - 匹配后返回最多 8000 字符，遇到下一个段落边界（全大写/首字母大写短行）提前截断
  - 未匹配返回 None

#### `app/utils/dates.py`
- **新增** `parse_date(value) -> date | None`
  - 基于 python-dateutil，支持 ISO、US long form 等多种格式
  - 解析失败返回 None，不抛异常
- **新增** `add_days(value, days) -> str | None`
  - 对 parse_date 结果加 N 个日历天，返回 ISO 字符串
  - 源字符串不可解析时返回 None
- **新增** `today_str() -> str`
  - 返回当天 ISO 日期字符串（YYYY-MM-DD）

### 修改文件

#### `app/config.py`
- 新增 `CACHE_DIR` property → `data/raw/cache/`
- 新增 `HTTP_TIMEOUT: float = 30.0`
- 新增 `HTTP_RATE_LIMIT_DELAY: float = 1.0`
- 新增 `HTTP_MAX_RETRIES: int = 3`
- 新增 `SEC_USER_AGENT: str`（默认 `"ipo-tracker research@example.com"`，可通过 `.env` 覆盖）

#### `requirements.txt`
- 新增 `httpx>=0.27.0`
- 新增 `tenacity>=8.2.0`
- 新增 `selectolax>=0.3.17`
- 新增 `lxml>=5.0.0`
- 新增 `truststore>=0.9.0`（修复 macOS conda 环境 SSL 证书验证失败问题）

### 不变文件
- `app/models.py` / `app/schemas.py` / `app/db.py` — 无需修改
- `scripts/init_db.py` — 无需修改（缓存目录按需由 http.py 自动创建）

---

## [Step 2] - 2026-03-11 — 数据库模型层

### 修改文件

#### `app/models.py`
- **重构** `Issuer` 模型：
  - `created_at` / `updated_at` 类型从 `DateTime` 改为 `Text`，与规格文档一致（时间字段统一用字符串）
  - 移除 `String(N)` 长度限制，改为 `Text`（SQLite 不强制列宽）
  - 新增 `filings` / `offerings` / `capitalizations` / `lockups` 四个 `relationship`，级联删除子记录
- **新增** `Filing` 模型（`filings` 表）：
  - 字段：`issuer_id`、`accession_no`、`form_type`、`filing_date`、`primary_doc_url`、`filing_index_url`、`is_parsed`、`created_at`
  - `UNIQUE(issuer_id, accession_no, form_type)` 约束，防止重复写入
  - 与 `Issuer`、`Offering`、`Capitalization`、`Lockup` 建立双向 relationship
- **新增** `Offering` 模型（`offerings` 表）：
  - 完整发行字段：价格区间、发行价、定价日、份额明细、greenshow、bookrunners 等
  - `bookrunners` 以分号分隔字符串存储
- **新增** `Capitalization` 模型（`capitalization` 表）：
  - 字段：`shares_outstanding_pre/post_ipo`、`free_float_at_ipo`、`float_ratio`、`fully_diluted_shares`
- **新增** `Lockup` 模型（`lockups` 表）：
  - 字段：`lockup_days`、`lockup_start/end_date`、`is_staged_unlock`、`unlock_notes`、`unlock_shares_estimate`、`confidence`

#### `app/schemas.py`
- **重构** 全部 schema，统一命名为 `XxxCreate` / `XxxRead` 格式
- **保留** `IssuerCreate`；将原 `Issuer` read schema 重命名为 `IssuerRead`
- **新增** `FilingCreate` / `FilingRead`
- **新增** `OfferingCreate` / `OfferingRead`
- **新增** `CapitalizationCreate` / `CapitalizationRead`
- **新增** `LockupCreate` / `LockupRead`
- 时间字段类型改为 `Optional[str]`，与模型层保持一致
- 移除 `IssuerUpdate`（当前阶段未使用，后续按需恢复）

#### `README.md`
- 更新安装说明，增加 conda 环境示例
- 增加升级提示（从 Step 1 升级需删除旧 DB）
- 增加数据库表结构说明
- 更新当前进度列表

#### `CHANGELOG.md`（新增）
- 新增本文件，记录各阶段变更

### 不变文件
- `app/config.py` — 无需修改
- `app/db.py` — 无需修改
- `scripts/init_db.py` — 无需修改（`create_all` 自动感知新模型）
- `app/utils/logging.py` — 无需修改
- `requirements.txt` — 无需修改

---

## [Step 1] - 2026-03-10 — 工程骨架

### 新增文件
- `requirements.txt`
- `README.md`
- `app/__init__.py`
- `app/config.py` — pydantic-settings 配置类，含路径和日志级别
- `app/db.py` — SQLAlchemy engine、SessionLocal、Base、get_db()
- `app/models.py` — 最小 `Issuer` 占位模型
- `app/schemas.py` — 最小 `IssuerCreate` / `IssuerRead` 占位 schema
- `app/collectors/__init__.py`
- `app/parsers/__init__.py`
- `app/jobs/__init__.py`
- `app/utils/__init__.py`
- `app/utils/logging.py` — `get_logger(name)` 工具函数
- `scripts/init_db.py` — 创建目录 + `Base.metadata.create_all`
- `tests/__init__.py`
