# News2Market 发布到 GitHub（中文版）

## 你当前拥有的两个目录不能混淆

- `~/Desktop/projects/News2Market/`：你的**原始实验目录**，包括 30 篇新闻抓取和历次完整结果。不要删除或直接用 ZIP 覆盖。
- 从 `News2Market_GitHub_Ready_2026-11-05.zip` 解压出来的 `News2Market/`：**准备公开的代码和研究摘要**，没有重新分发网页正文、金融字典或历史行情。

## 发布步骤（Mac）

1. 从 ChatGPT 下载发布 ZIP 到 `~/Downloads/`。
2. Finder 双击解压，或在 Terminal 执行：

   ```bash
   mkdir -p ~/Desktop/projects/News2Market_Public
   unzip ~/Downloads/News2Market_GitHub_Ready_2026-11-05.zip -d ~/Desktop/projects/News2Market_Public
   cd ~/Desktop/projects/News2Market_Public/News2Market
   ```

3. 在公开副本检查离线测试：

   ```bash
   python -m pip install -r requirements.txt
   python -m unittest discover -s tests -v
   ```

   正常情况下测试应显示 16 项通过、1 项因未公开五年真实价格数据而跳过。这是预计行为。

4. 登录 GitHub，在网站上创建新的**空仓库** `News2Market`（不要勾选自动创建 README 或 LICENSE）。代码的发布授权请选择你确实愿意采用的许可证；本包并未预先替你选择。
5. 在 Terminal 中进入公开副本后：

   ```bash
   git init
   git add .
   git status --short
   git diff --cached --stat
   git diff --cached
   ```

   **在提交之前请先核查**：不得出现下载的 Loughran–McDonald 字典、原始市场价格 CSV、抓取的新闻全文、API 密钥、个人本地路径或邮箱等敏感信息。ZIP 已预先排除上述数据，但你后续放入的文件也需要检查。

6. 核对没有限制数据后：

   ```bash
   git commit -m "Initial public News2Market research pilot"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/News2Market.git
   git push -u origin main
   ```

   把 `YOUR_USERNAME` 改为你自己的 GitHub 用户名。GitHub 可能要求使用 Credential Manager / 浏览器授权 / SSH；不要把账号密码写进命令行。

## 后续更新研究结果

新的自动抓取新闻不一定代表研究上的可用样本：必须先确认来源、日期、正文完整性和时间点。**不要把没有时间戳审核的文章直接合并进收益回归。** 公开材料中的10篇参考标注是AI辅助的，不能宣称真实人工标注。

## 如果测试失败

请把 Terminal 的第一段 `ERROR` 或 `FAILED` 内容发给我。不要直接复制旧项目完整 `Results/` 到公开仓库。
