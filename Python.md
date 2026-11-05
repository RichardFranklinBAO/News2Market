# News2Market v2.2 — 首先阅读 V2.2_NEW.md

**v2.2 新增本地免费 LLM、已抓取数据的 `--llm-only`、GDELT+少量外部 HTML 提取，以及原始 LM vs 清洗正文 LM 对照。**

请先看项目根目录的 `V2.2_NEW.md`，下面保留旧版价格、SEC 和论文方法的说明。

---

# News2Market v2.1 Free Edition — 五年 Nasdaq CSV 整合版（中文运行指南）

> 研究目标：将**真实公开文本**转成可审计的 LM 金融情绪指标，再与下一交易日收益进行**探索性关联分析**。这不是交易策略、收益预测保证或因果识别。
>
> **零付费 API / 零 GPT 费用 / 零自动 Yahoo 请求。** 默认 Demo 不联网；Live 的价格由用户提供的本地 CSV 读取。SEC / NVIDIA Newsroom / 可选 GDELT 不要求 API Key，但联网权限与使用政策因站点而异。你应有权获取并用于研究这些资料。

## 1. 项目文件夹（所有独立 Python 脚本在 Scripts）

```text
News2Market/
├── Python.md                        ← 读我：操作说明（Markdown 不能直接执行）
├── README.md                        ← 英文概览和研究限制
├── run_all.py                       ← 唯一总控入口：python run_all.py
├── requirements.txt
├── Inputs/
│   ├── config.yaml
│   ├── Loughran-McDonald_MasterDictionary_1993-2025.csv   ← 你需要放入官方真实 CSV
│   ├── prices/
│   │   ├── NVDA.csv                 ← 用户上传的 Nasdaq 5 年真实历史价格（2021–2026）
│   │   ├── QQQ.csv                  ← 用户上传的 Nasdaq 5 年真实历史价格（2021–2026）
│   │   ├── SOURCE_MANIFEST.json     ← 两份原始 CSV 的哈希、文件来源与日期范围
│   │   └── EXAMPLE_FORMAT.csv
│   ├── cache/                       ← 可缓存 SEC 公司代码映射
│   ├── demo_articles.csv            ← 首次 Demo 运行时自动生成（虚构）
│   └── demo_prices.csv              ← 首次 Demo 运行时自动生成（虚构）
├── Scripts/
│   ├── 00_resolve_company.py        ← ticker → 公司全名、CIK
│   ├── 01_discover_sources.py       ← SEC 申报清单 / 可选 GDELT 元数据
│   ├── 02_scrape_articles.py        ← NVDA 官方新闻正文的真正 HTML scraping
│   ├── 03_collect_filings.py        ← SEC 申报 HTML 正文提取
│   ├── 04_clean_deduplicate.py      ← 正文清洗 + URL、文本哈希去重
│   ├── 05_lm_sentiment.py           ← 官方 Loughran–McDonald 词典评分
│   ├── 06_event_tags.py             ← 免费、未验证的规则式事件标签
│   ├── 07_get_prices.py             ← 本地真实行情 CSV，绝不调用 Yahoo
│   ├── 08_build_signals.py          ← 日期映射、每日指标、下一时段收益
│   ├── 09_validate.py               ← 描述统计、OLS、图、人工审计模板
│   ├── common.py                    ← 工具函数
│   ├── lm_dictionary.py             ← 全词词典解析和命中词日志
│   ├── nvidia_scraper.py            ← requests + BeautifulSoup + robots
│   ├── signal_core.py               ← 时间对齐和收益计算
│   ├── create_demo_inputs.py        ← 仅用于虚构测试
│   └── get_lm_dictionary.py         ← 可选官方词典下载（可能被 Drive 限流）
├── Results/
│   └── TICKER/RUN_TIMESTAMP/        ← 每次运行独立输出，防止覆盖
└── tests/
    └── test_pipeline.py
```

## 2. 第一次安装（Mac / Terminal）

用 VS Code / Terminal 切换到 `News2Market/` 根目录，注意不是 `>>>` Python 交互环境：

```bash
python -m pip install -r requirements.txt
```

**词典位置**：`Inputs/Loughran-McDonald_MasterDictionary_1993-2025.csv`。你在 v1.2 时已下载的 CSV 可以**复制**过来，不需要重新从 Google Drive 下载。官方来源：[Notre Dame LM Master Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/)；仅按其学术研究使用条件使用。完整官方词典没有打包进此 ZIP，不能用示例词代替。

验证代码单元测试：

```bash
python -m unittest discover -s tests -v
```

**运行完整离线 Demo（虚构文章 + 虚构价格 + 真实 LM 词典）：**

```bash
python run_all.py
```

Demo 若成功，会出现 `SUCCESS`，但所有价格和文本仍然是 `SYNTHETIC DEMO`，绝不是市场证据。Demo 不需要 `Inputs/prices` 中的真实价格。

## 3.0 本次上传的五年行情（已内置）

| 代码 | 本地 CSV | 原文件 | 起止日期 | 有效交易日 |
|---|---|---|---|---|
| NVDA | `Inputs/prices/NVDA.csv` | `HistoricalData_1793873066194.csv` | 2021-11-05 至 2026-11-04 | 1254 |
| QQQ | `Inputs/prices/QQQ.csv` | `HistoricalData_1793873082665.csv` | 2021-11-05 至 2026-11-04 | 1254 |

价格数据的 Nasdaq 典型格式为 `Date,Close/Last,Volume,Open,High,Low`，日期是月/日/年，可带美元符号。脚本 `Scripts/07_get_prices.py` 已直接兼容此格式且会升序排列，无须把 `Close/Last` 改名为 `Adj Close`。原始数据不建议公开放到 GitHub，详见数据源条款。

**五年价格 ≠ 五年新闻：** 默认抓取文章窗口仍是 2026-08-01 到 2026-11-04。若想收集更久的文本，请改 `--start/--end` 并核实网站历史覆盖。对于价格截止日 2026-11-04 及之前一两个交易日的最新文章，可能因为缺少随后两个交易日的收盘价而无法构造下一交易日收益——程序会跳过，不会编造未来价格。

## 3. 真实 NVIDIA：先收文本，再补免费价格 CSV

**建议分两步做，避免 Yahoo 限流：**

```bash
python run_all.py --mode live --ticker NVDA --max-articles 10 --collect-only
```

该命令只进行：NVDA 身份确认 → Newsroom 网页列表 → 真实新闻 HTML 正文 → 清洗 → LM 词典 → 事件标签。**不会**访问 Yahoo，也不需要真实价格 CSV。成功后输出 `Results/NVDA/<本次时间戳>/`，`Results/NVDA/LATEST.txt` 会记录最近一次运行的文件夹名称。

本 v2.1 包已经放入你刚上传的两份真实 Nasdaq 历史价格 CSV，不需要再手工改列名或日期格式。文件位置：

- `Inputs/prices/NVDA.csv`
- `Inputs/prices/QQQ.csv`

我们已经按价格尺度识别第一份（约 $200）为 NVDA，第二份（约 $690）为 QQQ，并保留原始格式。**文件本身没有 Ticker 字段，因此股票身份还应以你下载时的网站标的核验。** 程序已校验：两份均有 1254 行，日期 2021-11-05 至 2026-11-04，完全匹配。运行审计会记录 SHA256。**绝对不要把 demo_prices.csv 当成真实数据。**

**每个文件单独一份，最简单的格式：**

```csv
Date,Adj Close
2026-08-03,123.45
2026-08-04,124.56
```

以上数字是**格式示例，完全虚构，不是 NVIDIA 真实价格**。真实文件应覆盖新闻起止日期，且往后多包含数个交易日以计算下一期收益；本次提供完整五年日线。

支持日期字段 `Date` 的 `YYYY-MM-DD` 和 Nasdaq 的 `MM/DD/YYYY`；支持 `Adj Close` / `Adjusted Close` 或 `Close` / `Close/Last`，并能读取带 `$` 的价格。两份上传文件的 `Close/Last` **不是现金分红调整后的 Adj Close**；因此回归是 NVDA 减 QQQ 的**收盘价格收益率差**，不是分红总回报差。NVDA 在 2024-06-07 和 2024-06-10 为 120.888 和 121.79，数值表明拆股前后已处于同一尺度，但这不等于股息调整已核实。

放好以后，继续之前的真实新闻数据，不需要重抓：

```bash
python run_all.py --mode live --ticker NVDA --resume
```

`--resume` **只复用最近一次完整完成文本标签阶段的同一 ticker、benchmark、mode**。缺价格时保留原始结果，等你补好再继续。数据来源检查请看 `07_price_audit.json`。

想多抓一点：

```bash
python run_all.py --mode live --ticker NVDA --max-articles 30 --collect-only
```

运行时限制最多 50 篇，最多 8 个列表页，并尊重 robots.txt、请求间隔和单页大小上限。

## 4. 输入其他美股代码（SEC 为默认全文来源）

对于 **NVDA**，`--source auto` 默认使用 NVIDIA Newsroom 真正的 HTML 网页抓取。对于 **其他在 SEC ticker mapping 中存在的美国上市公司**，`--source auto` 默认改为 SEC EDGAR 的 8-K、10-Q、10-K 等正式公开申报全文，**不**会把 NVIDIA 的新闻归给其他股票。

SEC 官方要求机器人提供可联系的真实 User-Agent（个人/单位及邮箱），请先在**同一个 Mac 终端窗口**设置：

```bash
export N2M_SEC_USER_AGENT="Your Actual Name your-real-email@domain.com"
```

上面的地址只是占位符，**请替换成你真实的联系人信息**。项目 `.env.example` 仅为示例，不会自动加载。

之后运行：

```bash
python run_all.py --mode live --ticker AAPL --source sec --max-articles 10 --collect-only
```

这里 `AAPL` 是示例；也可以改成 `MSFT`、`JPM` 等有 SEC 标识的美国上市公司。默认日期在 `Inputs/config.yaml`，也可以参数覆盖：

```bash
python run_all.py --mode live --ticker MSFT --start 2026-08-01 --end 2026-11-04 --collect-only
```

若要实证分析 `AAPL` 对 `QQQ`，把真实 `AAPL.csv`、`QQQ.csv` 放进 `Inputs/prices/`，执行：

```bash
python run_all.py --mode live --ticker AAPL --resume
```

**当前支持范围有意保守**：NVDA 的真实官方 Newsroom + 其他 SEC 公司可用的申报正文。输入“任意代码”的意思是可以尝试识别**SEC 映射覆盖的美国股票**，而不是保证每家公司都能找到 50 条新闻或足够的 8-K。SEC 申报不等同于财经媒体新闻。对于 A 股、港股、ETF、加密货币、退市公司或没有 SEC 记录的股票，本版不承诺支持。

## 5. 可选 GDELT 新闻发现（不等于抓到正文）

```bash
python run_all.py --mode live --ticker NVDA --gdelt --max-articles 10 --collect-only
```

`01_gdelt_metadata_only.csv` 会存发现的标题、URL、网站和时间。**该文件不参与 LM 打分、不被当成真实全文。** GDELT 搜索存在时间覆盖范围、速率和公开文章来源差异；未经许可不自动去抓任意媒体的付费正文。用户可对合理可访问来源另写专用解析器并人工审核。

## 6. 论文依据和情绪指标

LM 原词典提供七类金融文本标签：Negative、Positive、Uncertainty、Litigious、Strong Modal、Weak Modal、Constraining。脚本采用**词频按字符截断后的完整英文词匹配**，不做词干扩展，不做神经网络或 GPT。记录七类词频/每千词、前三类实际命中词、官方 CSV 的 SHA-256。

我们定义（**是项目的操作化指标，不是 LM 原论文唯一规定的公式**）：

\[
score_i=\frac{P_i-N_i}{P_i+N_i}.
\]

没有命中任何 Positive 或 Negative 词时记为**缺失**，而不是强行标成零。每天将可打分文章的 score 简单平均得到 `sentiment_score`，并记录 `news_count`。规则式事件类型仅作辅助说明，**不是经过独立验证的经济机制或 GPT 分类**。

LM 原本更适用于金融披露，迁移到新闻/官方 PR 的适用性需要通过人工检查、不同文本来源比较等方式检验。

## 7. 避免未来信息泄漏

当前只有**发布日期**，没有逐篇准确发布时间。保守做法为：文章发布日之后的**第一个交易日收盘**才形成信号；用再下一个交易日的收盘收益计算股票减基准差。见 `08_alignment_audit.json`。这并不等于真实可交易策略，也不证明新闻导致收益变化。

OLS 只有有效信号日数达到 8、情绪具有变化时才估计；HC1 只是异方差稳健，不是序列相关稳健；没有 out-of-sample 验证，不可声称预测能力。SEC 10-K 或 10-Q 长文本可能有免责声明和复杂 HTML，需要人工审阅抽样段落。

## 8. 检查输出（最重要的几个文件）

- `00_company.json`：SEC CIK、公司名字和解析依据。
- `02_web_articles.csv`：NVIDIA 官方网页已成功解析的全文（仅 NVDA）。
- `03_filings.csv`：其他 SEC 公司抓取的申报正文。
- `04_articles.csv`：清洗去重后的正文；必须人工抽查。
- `05_lm_labels.csv`：官方 LM 七类金融词频、分数、命中词。
- `05_lm_audit.json`：官方词典版本和 SHA256。
- `06_labels_with_events.csv`：经济事件的**规则式暂定标签**。
- `07_prices.csv` + `07_price_audit.json`：来自本地 CSV 的真实交易日收盘数据及是否调整。
- `08_daily_signals.csv`：每日情绪、目标收益、交易日期映射。
- `09_analysis_summary.json`：相关性、OLS（若满足最小观测要求）、局限。
- `09_signal_vs_return.png`：散点图。
- `09_human_audit_template.csv`：手动抽样审查模板。
- `00_run_manifest.json`：**是否完整成功**；不要将失败时残留的旧文件当成最终结果。

## 9. 常见问题

**Q：`gdown` 受限怎么办？** A：直接把你此前下载的官方 CSV 复制到 `Inputs`；主程序不会重新下载。

**Q：`YFRateLimitError`？** A：新版真实价格只读本地 CSV，根本不会调用 `yfinance`。

**Q：`Missing REAL market CSV`？** A：先运行 `--collect-only`，准备 `Inputs/prices/<ticker>.csv` 和 `QQQ.csv`，再 `--resume`。

**Q：SEC 403 / 429？** A：检查真实 `N2M_SEC_USER_AGENT`、网站可用性和访问政策；不要绕过访问限制。

**Q：真实数据但回归 `regression: null`？** A：常见原因是少于 8 个有效**信号日期**、词典命中太少、时间没有与行情重叠、或情绪分数没有变化。查看 audit 文件；不能为了跑出回归而虚构数据。

**Q：是否能分析全市场任意股票新闻？** A：还不能。当前稳定设计为 NVDA 官方 Newsroom 和 SEC 公开申报；GDELT 是链接发现。正式多媒体公司新闻抓取必须另加合规来源及每站点专用解析器。

## 10. 免费来源和参考

- [Notre Dame — Loughran–McDonald Master Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/)（免费学术研究使用，商业使用联系作者）
- Loughran, T. & McDonald, B. (2011). *When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks*. *Journal of Finance*, 66(1), 35–65.
- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC fair access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- [GDELT DOC API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)

### 推荐执行顺序

首先执行 `python run_all.py`（离线 Demo），再执行 `python run_all.py --mode live --ticker NVDA --max-articles 10 --collect-only`，人工核查 `04_articles.csv` 和 `05_lm_labels.csv`。此压缩包已包含所需的两份 5 年真实 Nasdaq 价格 CSV，收集真实新闻后使用 `--resume` 补完分析。每个阶段都有独立 CSV/JSON 可复查，不需要重新抓所有数据。
