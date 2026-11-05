# News2Market v2.2 — Free Local LLM + External Web Pilot

**免费原则**：整个自动化流程不使用 OpenAI API、收费搜索 API 或云模型。OpenAI GPT 和 Ollama 本地模型不是同一种模型；GPT 可以在 ChatGPT 对话内用于小样本人工审查，自动批处理若坚持零 API 账单则用本地模型。

## 1. 在已经抓到 30 篇真实 NVIDIA 新闻的旧项目中使用

推荐下载 **v2.2 补丁包**并把其中文件覆盖原来的同名文件。**不要删除 `Results/` 和 `Inputs/`**：原始 LM 词典、5 年价格和 30 篇已抓取的新闻都能继续使用。

```bash
cd ~/Desktop/projects/News2Market
python -m pip install -r requirements.txt
```

**先独立测试清洗和 LM 对照（不用 Ollama）：**

```bash
python run_all.py --mode live --ticker NVDA --clean-only
```

这会生成 `11_nlp_ready_articles.csv` 与 `11b_lm_original_vs_cleaned.csv`，原始文章及 LM 文件保留不变。

**之后尝试本地 LLM，不重新爬新闻、不下载行情：**

首先安装 Ollama 桌面应用：https://ollama.com/download
在本机下载一个免费模型（约 1.9GB 磁盘）：

```bash
ollama pull qwen2.5:3b
ollama list
```

打开 Ollama App；如果服务未运行，可用 `ollama serve` 启动。随后在项目根目录执行：

```bash
python run_all.py --mode live --ticker NVDA --llm-only --llm-model qwen2.5:3b --llm-max-articles 3
```

命令会读取 `Results/NVDA/LATEST.txt` 指向的已有运行结果，生成：

- `11_nlp_ready_articles.csv`：保留原文且新建一个剔除已知 NVIDIA 页脚的 `narrative_text` 列。
- `11b_lm_original_vs_cleaned.csv`：官方 LM 词典在原始正文与清洗正文的情绪测量对照。
- `12_local_llm_labels.csv`：本地模型识别的事件类型、经济机制、-1~1 情绪得分、证据句、验证结果。
- `12_local_llm_audit.json`：模型、有效标签数量和失败记录。

若 3 篇测试正常，再运行 `--llm-max-articles 10`，随后 30。该分数是对公司预期经营基本面的文本判断，不是可交易的价格预测；不自动并入 LM 回归。

如果 Mac 较旧、内存不足，可先下载较小的模型：`ollama pull qwen2.5:1.5b`，然后用 `--llm-model qwen2.5:1.5b`。小模型可能降低结果质量。所有 `:cloud` 模型都被显式禁止。

## 2. 尝试整个互联网的信息：小规模、可审计、合规的 Discovery + Web Extraction

**“整个互联网”无法穷尽**，特别是付费墙、禁止爬取的网站，以及索引未覆盖的历史网页。新增 `--web-news` 会使用 GDELT 搜索近期公司新闻链接，并在满足 HTTPS 安全、robots.txt 许可、长度、日期与标题相关性条件时，尝试抓取少量第三方 HTML 正文。每个外部站点最多 2 条，默认最多 10 条，**不破解付费墙、不无限翻页、不保证抓取成功**。

```bash
python run_all.py --mode live --ticker NVDA --max-articles 10 --web-news --max-external 5 --collect-only
```

此命令会**创建新的结果运行目录**（不破坏上一次的数据），从 NVIDIA 官方 Newsroom 最多获取 10 篇新闻，同时尝试 GDELT+外部站点最多 5 篇；保存：

- `01_gdelt_metadata_only.csv`：GDELT 发现的标题和 URL，未声称正文可用。
- `03b_external_articles.csv`：真正抓到正文的外部网页，失败的不会冒充全文。
- `03b_external_audit.json`：每个失败/过滤原因与请求数。
- `04_articles.csv`：官方与外部已验证正文合并（保留 `source_type`）。

⚠️ GDELT DOC 2.0 只检索近期，脚本会把过早的起始日期收窄至最近 85 天，并明确打印调整提示。`published_date` 对外部媒体采用 GDELT **首次看到日期**的代理，绝不伪称已准确验证媒体首次发布时间。因此该日期适合谨慎的技术探索，不足以直接发表严谨的事件研究。

External `source_type=external_web_unverified` 表示尚未验证它是否真正独立报道、转载或者 PR 软文。后续需人工审核媒体独立性，避免与官方新闻混合解释。

对 AAPL/MSFT 等公司，可用 SEC Ticker Resolver 获得公司身份并抓取 SEC 公开申报；第三方新闻仍由 GDELT 搜索。**各家公司的官方新闻稿站点仍需逐站适配或维护可验证的 RSS/sitemap 源列表**，并非输入 ticker 就能自动覆盖所有官网。

## 3. 研究质量与局限

- NVIDIA 官网 30 篇示例文本中，29 篇可识别 `About NVIDIA` 新闻稿页脚，清理 95,989 字符（约 34.1%）。启发式裁剪必须人工抽查。
- 原始 LM/清洗 LM 与 LLM 可能测量不同概念：分别标记并评估，不因三者相关就断言有效。
- LLM 的 `evidence_quote` 只有在清洗后原文里逐字出现，才会输出可用于分析的 `sentiment_score`。无证据不会强加分数。
- 固定本地模型/提示词版本、温度 0 与输入哈希有助于复现，但不能保证跨硬件或版本完全相同。
- 真实新闻发布日期、首次被发现日期、价格可交易时点之间的差异需要独立核实；现有回归仍为探索性相关，非因果或交易策略。

## 4. 参考资料

- LM official: https://sraf.nd.edu/loughranmcdonald-master-dictionary/
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Ollama local API: https://github.com/ollama/ollama/blob/main/docs/api.md
- Trafilatura: https://trafilatura.readthedocs.io/en/stable/
