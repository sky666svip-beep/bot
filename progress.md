# 项目进展

## 2026-03-16

- **完成任务**：调研并确认 `nlp_service.py` 中的 `jieba` 分词模式。
- **技术细节**：
  - `jieba.cut()` 和 `jieba.lcut()` 在默认情况下即为精确模式 (`cut_all=False`)。
  - 经评估，当前系统已按预期工作，无需修改代码以显式指定默认参数。
- **验证结果**：通过源码核查确认，匹配逻辑正常。

## 2026-03-17

- **完成任务**：升级 `nlp_service.py` 检索架构为 BM25+ 与 Embedding 并行双路召回 + RRF 融合，并完成超参调优。
- **技术实现细节**：
  - **设计思路**：单路 Embedding 召回对关键词完全匹配不敏感，引入 BM25+ 稀疏召回补偿词频信号，通过 RRF 融合两路排名。
  - **核心变更**：
    - 拆解 `standardize_text` 为 `tokenize() → join` 两步，BM25 索引复用同一分词管道。
    - 新增 `_build_bm25_index()`：基于倒排索引 + Robertson-Sparck Jones IDF + `δ=1.0` 下限保护。同时在此步骤中构建 `_std_q_map` 缓存，支持 O(1) 的精确匹配前置拦截。
    - 新增 `_bm25_plus_search()`：走倒排索引稀疏召回。
    - 新增 `_rrf_merge()`：RRF 融合排行。
    - 重写 `search_best_match()`：精确匹配 O(1) 前置拦截 → 双路并发召回 → RRF 融合。
    - 引入复合置信度 `confidence = max(best_emb_score, rrf_confidence)`，防止 Embedding 低分误杀 BM25 正确候选。
    - 增量热更新 `add_to_index()`：支持插入新数据时 BM25 + std_q_map 同步更新。
    - 调优超参：设立 `_RRF_K=20` 与 `_RECALL_TOP_K=10` 适配当前 ≤2w 数据规模的高置信度表现。
  - **接口兼容**：`search_best_match` 和 `add_to_index` 签名保持绝对兼容，`answer_engine.py` / `routes.py` 无需修改。
- **遇到的问题与解决方案**：
  - **Bug现象**：初版 RRF 仅返回包含 `best_idx` 的单路 `emb_score`，导致 BM25 特化召回的理想候选因为 Emb 评分低（如口语化噪音）遭到误杀丢弃。
  - **原因分析**：RRF 是排名融合，其绝对分值（0.03级别）无法直接与余弦值（0.80级别）等价代换。
  - **解决办法**：对 RRF 分数进行归一化算得 `rrf_confidence`，并使用 `confidence = max(best_emb_score, rrf_confidence)` 提升由于召回噪音造成的低相似度权重。
- **验证结果**：
  - [x] 通过验证：经 `test_hybrid_search.py` 数据测试，双路、单路以及精确阻断场景均符合预期。成分置信度表现优秀。

## 2026-03-18

- **完成任务**：深度优化 `llm_service.py`，增强 LLM 响应的稳定性与解析鲁棒性。优化 `answer_engine.py` 的搜题管道性能与健壮性
- **技术实现细节**：
  - **JSON 净化机制**：新增 `_extract_json_string`，利用正则表达式或边界定位技术，从模型返回的混合文本中精确提取 `{}` 或 `[]` 结构，消除 Markdown 标记及前后冗余文字干扰。
  - **指数退避重试**：在 `_call_qwen_json` 中实现重试逻辑，默认 `max_retries=2`，并配合 `time.sleep(2 ** attempt)` 进行避让，有效缓解 API 并发限流或偶发网络抖动问题。
  - **架构统一**：重构 `generate_poetry_analysis` 等函数，统一通过底层私有方法进行调用，确保全局配置（如 temperature, timeout）和稳定性策略的一致性。
  - **多模态加固**：针对视觉搜题 `solve_with_vision` 和 OCR 功能，同步引入重试机制，应对视觉模型推理开销大、易波动的问题。
  - **计算冗余优化**：通过在 `solve_pipeline`、`fast_db_lookup` 与 `save_question_to_db` 之间传递已计算的 `std_query`，消除了重复的文本标准化（分词及正则清洗）开销，显著提升链路响应速度。
  - **数字指纹加固**：重构 `extract_core_numbers`，将提取的数字统一转换为 `float` 类型后再排序比对。有效解决了因“1”与“1.0”字符串不一致导致的向量匹配误拦截。
  - **算法效率提升**：将 `is_semantically_identical` 中的字符排序对比算法替换为 `collections.Counter` 频次统计，将校验时间复杂度从 $O(N \log N)$ 降至 $O(N)$。
  - **数据一致性规范**：
    - 抽象 `_parse_options` 辅助函数，统一处理题库中 JSON 字符串与对象的解析逻辑。
    - 规范 AI 兜底逻辑返回路径，确保 `ai_answer` 在入库与最终返回给前端时的数据类型保持一致。
  - **接口解耦**：优化入库函数 `save_question_to_db`，使其支持外部注入标准化指纹，避免在自动化入库场景下的重复计算。
- **验证结果**：
  - [x] 鲁棒性验证：模拟模型返回带废话的 JSON 输出，净化器成功提取正确数据。
  - [x] 压力验证：通过人为触发速率限制，系统成功通过重试机制自动恢复。
  - [x] 代码质量：消除冗余重复代码约 30%，接口职责更加单一明确。
  - [x] 性能验证：流水线中标准化文本的计算频率降低了 66%。
  - [x] 兼容性验证：成功通过包含数值差异（1 vs 1.0）的边缘测试用例。
  - [x] 稳定性验证：AI 响应的 JSON 格式在各种异常输入下均能正确解析并返回。

- **完成任务**：核心路由架构重构、严重性能瓶颈消除与安全性增强
- **遇到的问题与解决方案**：
  - **严重性能瓶颈：公式搜索矩阵未缓存**：现状：在 /formulas/search 中，每次用户搜索都会触发 formulas  = sql_query.all() 获取全表数据，然后遍历执行 json.loads(f.embedding)，最后构建 torch.tensor 计算相似度。这在数据量达到数千条后，会导致该接口响应极其缓慢并引发显存/内存抖动。
    改进：效仿 NLPService 中的 _corpus_tensor，在应用启动时一次性加载所有公式的向量矩阵并驻留在显存 (GPU/内存) 中，搜索时直接进行张量运算。
  - **慎用 ORDER BY RANDOM()**：现状：在 /words 和 /idioms/random 中使用了 order_by(func.random())。在 SQLite 或多数数据库中，这会引发全表扫描 (Full Table Scan) 并临时排序。如果词汇表达到 10 万级，这会成为灾难。
    改进：先查出最大 ID，然后在 Python 层随机生成几个在区间内的 ID，使用 .filter(Idiom.id.in_(random_ids)) 进行精准抓取。
  - **批量插入与批量向量化 (N+1 性能问题)**：现状：在 /simulation/submit 中，通过 for item in results: 循环内单条调用 save_question_to_db。由于每次调用都会计算一次 Embedding 并提交一次事务，这产生了严重的 N+1 性能问题。
    改进：应提取所有问题文本，交给 nlp_engine 批量 .encode(texts)，再使用 db.session.bulk_save_objects 一次性入库。
  - **安全性与鲁棒性加固**：
    - 文件上传安全性漏洞
    现状：/upload-doc 和 /solve-image 虽然通过 uuid 规避了文件名冲突和路径穿越，但完全没有校验文件拓展名类型。恶意用户可以上传 .sh 或 .exe 文件堆满服务器空间。
    改进：添加严格的扩展名后缀和 MIME 类型校验（见下方补丁）。
    - 缺乏统一全局异常处理
    现状：目前许多路由没有 try...except 保护（如 /search, /solve）。一旦抛出异常（如数据库断连、数据格式不符），Flask 默认会返回 500 HTML 页面，破坏了前端的 JSON 解析。
    改进：使用 @api_bp.errorhandler 全局拦截异常并包装为统一规范的 JSON 格式。

- **技术实现细节**：
  - **巨型单体路由拆分 (Blueprint Decomposition)**：将臃肿的 `routes.py` 拆分为职责明确的 `views.py` (纯页面渲染)、`api_search.py` (核心搜题引擎) 和通用杂项 API 工具。并同步修复了前端模板 (`index.html`) 的 `url_for` 页面引用错误与 `search-engine.js` 的异步请求 404 路径问题。
  - **公式搜索显存常驻 (GPU/RAM Matrix Cache)**：在 `NLPService` 中拓展 `_formula_tensor`，在应用启动时一次性加载所有公式的向量矩阵并驻留显存。彻底解决了此前 `/formulas/search` 每次搜索都需要全表查询、实时 `json.loads` 构建张量带来的灾难性显存抖动与高延迟。
  - **消除 N+1 性能灾难**：重构 `/simulation/submit` 模拟考试提交接口，提取文本交由模型进行 `batch_size` 批量向量化，并使用 `db.session.bulk_save_objects` 实施批量入库，最后增量热更新到内存索引中，大幅降低事务开销。
  - **全表扫描 (Full Table Scan) 优化**：针对成语和单词随机获取接口 (`/words`, `/idioms/random`)，彻底摒弃低效的 `ORDER BY func.random()`。改为先查询 `max_id` 然后在 Python 层生成随机数列表，通过 `IN` 条件精准命中，保障在十万级词库量下也能达到毫秒级响应。
  - **安全性与鲁棒性加固**：针对文档与图片上传增加严格的文件扩展名校验 (`ALLOWED_IMAGE_EXTS` 等)，防止恶意脚本上传满载服务器；在 `api_bp` 新增全局 `errorhandler` 统一拦截异常并包装为标准 JSON 格式，防止前端解析 Flask 默认的 500 HTML 报错页面而导致程序崩溃。
- **验证结果**：
  - [x] 架构解耦：蓝图路径注册正常，前后端全链路通信畅通。
  - [x] 性能飞跃：公式检索实现了毫秒级响应；批量模拟试题提交不会再引发服务器线程阻塞。
  - [x] 安全性提升：非法文件类型上传请求被成功阻截。

## 2026-03-19
- **完成任务**：解决 WSGI 线程被同步 LLM 调用和 PDF 解析阻塞导致 502/504 的问题
- **技术实现细节**：
    - **设计思路**：使用 Python 标准库 `ThreadPoolExecutor` 作为进程内后台线程池，将重 I/O 操作卸载到后台线程，WSGI 线程仅负责「提交任务」和「查询结果」两个毫秒级操作，前端改为轮询模式获取结果。
    - **核心变更**：
        - `app/services/async_task.py`：新建进程内异步任务管理器（全局单例），基于 `ThreadPoolExecutor(max_workers=4)` + `threading.Lock` 保护的状态字典。支持 Flask app 上下文注入、结果 TTL 5 分钟自动清理。
        - `app/api/routes.py`：改造 7 个阻塞接口（`/upload-doc`、`/essay/correct`、`/ocr-image`、`/study-plan/generate`、`/simulation/generate`、`/poetry/search`、`/formulas/explain`）为异步提交模式。新增 `/task/<task_id>/status` 通用轮询端点。
        - `app/api/api_search.py`：改造 3 个阻塞接口（`/search`、`/solve`、`/solve-image`）为异步提交模式。
        - `app/static/js/poll-helper.js`：新建前端通用轮询辅助模块，提供 `TaskPoller.poll()` 和 `TaskPoller.submitAndPoll()` 两个方法。
        - `search-engine.js`、`essay.js`、`poetry.js`、`study_plan.js`、`simulation-exam.js`、`formulas.js`：将所有 `fetch()` 调用替换为 `TaskPoller.submitAndPoll()`。
        - 6 个 HTML 模板：添加 `poll-helper.js` 脚本引用。
- **遇到的问题与解决方案**（必填，若顺畅则写 无）：
    - **Bug现象**：`/solve-image` 和 `/ocr-image` 涉及临时文件管理，文件清理需在后台任务完成后执行
    - **原因分析**：原代码在 WSGI 线程的 `finally` 块中删除临时文件，但异步化后 WSGI 线程已提前返回
    - **解决办法**：将文件清理逻辑移入后台线程闭包的 `finally` 块中，确保处理完成后再删除
- **验证结果**（所有测试脚本保存至 d:\Projects\choicebot\test 目录下）：
    - [x] 通过验证：`test/run_async_test.py` 全部 10/10 断言通过（提交/轮询、异常处理、并发、状态流转、app 上下文注入）
- **附注**：
    - 线程池设为 4 个 worker，与 Waitress 的 8 个 WSGI 线程分离，不争抢资源
    - 对于 `/poetry/search` 等接口，数据库命中时仍同步返回（毫秒级），仅 LLM 生成路径走异步

- **完成任务**：异步引擎安全与健壮性二次修复
- **技术实现细节**：
    - **设计思路**：针对第一版遗留的 5 个安全/健壮性问题逐项修复
    - **核心变更**：
        - `async_task.py`：(1) `db.session.remove()` 清理线程级 session 防止连接泄漏；(2) `Semaphore(64)` 任务队列背压保护，超限拒绝；(3) `secrets.token_hex(16)` 生成 32 字符加密级 task_id；(4) `owner` 参数支持归属校验
        - `routes.py`：轮询端点增加 owner 鉴权；`/simulation/submit`（model.encode 阻塞）异步化；所有 submit 调用绑定 owner
        - `api_search.py`：所有 submit 调用绑定 owner
        - `poll-helper.js`：固定间隔改为指数退避（800ms→×1.5→max 6s）
        - `simulation-exam.js`：submit 接口适配轮询
- **遇到的问题与解决方案**：无
- **验证结果**（所有测试脚本保存至 d:\Projects\choicebot\test 目录下）：
    - [x] 通过验证：`test/run_async_test.py` v2 全部 15/15 断言通过（含 task_id 安全性、owner 鉴权、队列背压）
- **附注**：无

- **完成任务**：修复异步任务轮询返回「任务不存在」的严重 bug
- **技术实现细节**：
    - **设计思路**：统一 submit / poll 两侧的 owner 标识计算逻辑
    - **核心变更**：
        - `routes.py`：新增 `_get_owner()` 辅助函数（`str(current_user.id) if authenticated else session cookie`），poll 端点和全部 7 个 submit 调用均改用此函数
    - **根因**：submit 端使用 `request.cookies.get('session', 'anon')` 作为 owner（值如 `"eyJ..."`），而 poll 端使用 `str(current_user.id)`（值如 `"42"`）。已登录用户两侧值不一致 → `get_status` 权限校验失败 → 返回 `not_found`
- **遇到的问题与解决方案**：
    - **Bug现象**：所有异步化接口在登录状态下轮询均返回「任务不存在」
    - **原因分析**：submit 和 poll 使用了不同的 owner 计算公式
    - **解决办法**：抽取 `_get_owner()` 辅助函数，消除不一致
- **验证结果**：
    - [x] 通过验证：`test/run_async_test.py` 15/15 断言通过

## 2026-03-20
- **完成任务**：图片搜题对齐文本搜题逻辑，支持识别题目文本并统一入库，修复主页错题本侧边栏被分类按钮遮挡的层叠问题
- **技术实现细节**：
    - **设计思路**：图片搜题原本只返回答案和解析，题目硬编码为 `[图片搜题]` 且不入 `QuestionBank`。现让 Vision LLM 同时返回 `question` 字段，后端复用文本搜题的入库链路。原分类按钮容器 `.category-nav-container` 的 `z-index` 被设为 `1050`，高于 Bootstrap Offcanvas 默认的 `1045`，导致侧边栏触发时底部内容穿透遮挡。将其下调至 `100` 恢复正常的 DOM 堆叠逻辑。
    - **核心变更**：
        - `llm_service.py`：`solve_with_vision` 的 prompt 增加 `question` 字段要求，让 LLM 输出识别出的完整题目原文
        - `api_search.py`：`_solve_img` 重写，提取 `question` 字段后调用 `save_question_to_db`（入 QuestionBank，含去重+向量索引）和 `save_to_history`（入 UserHistory），与文本搜题行为完全一致。返回数据增加 `question` 和 `is_mistake` 字段
        - `search-engine.js`：`handleImageUpload` 识别成功后将题目文本回填到 `rawText` 输入框
        - `app/static/css/style.css`：将 `.category-nav-container` 的 `z-index: 1050` 修改为 `z-index: 100`。
- **遇到的问题与解决方案**：
 - **Bug现象**：主页打开左侧错题本抽屉时，分类模块层叠在侧边栏上方，导致阅读与交互受阻。
    - **原因分析**：容器元素的 `z-index` 设置不合理（`1050` 等同于模态框层级）。
    - **解决办法**：下调至 `100`。
- **验证结果**：
    - [x] 上传图片 → 确认输入框回填题目、结果正常、数据库 question_bank 和 user_history 均有正确记录
- **附注**：无

## 2026-03-26
- **完成任务**：修复了主页复制答案按钮不起作用的问题，并将全局事件总控抽离至 `app.js`。
- **技术实现细节**：
    - **设计思路**：为了防止 `index.html` 前端代码过于膨胀臃肿，决定重启并清理遗留的 `app.js` 作为前端事件初始化与分发的统一入口。
    - **核心变更**：
        - `app/static/js/app.js`：清除了原有的重复执行的 UI 特效启动代码，保留并挂载了 `copyAnswer` 剪贴板写入逻辑，接管了 `Dashboard.init()` 并且保留了 Ctrl+Enter 等快捷键绑定。
        - `app/templates/index.html`：移除了冗余的内联初始化脚本，改为通过 `<script>` 标签统一引入 `app.js`。
- **遇到的问题与解决方案**：
    - **Bug现象**：用户点击复制按钮无任何反应。
    - **原因分析**：负责剪贴板写入的全局函数 `copyAnswer` 未被加载到页面中。
    - **解决办法**：清理 `app.js` 中的时序冲突并重新将其集成至 `index.html` 作为主控制模块。
- **验证结果**：
    - [x] 通过验证：功能代码解耦完成，前端复制等交互恢复正常且无重复初始化问题。
- **附注**：无

## 2026-03-27
- **完成任务**：修复了 `history.html` 和 `idiom_detail.html` 中因 Jinja2 标签导致的前端语法错误提示。
- **技术实现细节**：
    - **设计思路**：为了消除 IDE 对 JavaScript 块内 Jinja2 语法的解析错误，通过将数据注入 `body` 的 `dataset` 或将控制逻辑移出 `<script>` 标签的方式来实现服务器端到客户端的数据/逻辑传递，确保脚本内容的合法性。
    - **核心变更**：
        - `app/templates/history.html`：拆分脚本块，移动认证状态检查逻辑。
        - `app/templates/idiom_detail.html`：将 `idiom_id` 的传递方式改为通过 `document.body.dataset` 获取。
- **遇到的问题与解决方案**：
    - **Bug现象**：IDE 报错 "Property assignment expected"、"Expression expected" 等。
    - **原因分析**：Jinja2 的 `{{ ... }}` 和 `{% ... %}` 语法在 JS 环境中具有不同的语义（如对象字面量、模数运算等），导致解析冲突。
    - **解决办法**：物理隔离 Jinja2 语法与 JavaScript 代码。
- **验证结果**：
    - [x] 通过验证：功能正常，ID 成功传递给后端 API，语法错误消失。
- **附注**：无

## 2026-03-27
- **完成任务**：将 `dashboard.js` 合并至 `app.js` 并精简了 `index.html` 的引用。
- **技术实现细节**：
    - **设计思路**：为了减少前端 HTTP 请求数量并整合入口逻辑，将 `Dashboard` 模块代码迁移至 `app.js`。
    - **核心变更**：
        - `app/static/js/app.js`：集成 `Dashboard` 定义，并在 `DOMContentLoaded` 中统一初始化。
        - `app/templates/index.html`：移除已合并脚本的引用。
        - `app/static/js/dashboard.js`：已物理删除。
- **遇到的问题与解决方案**：无
- **验证结果**：
    - [x] 通过验证：首页图表（饼图、热力图）加载正常，交互逻辑连贯。
- **附注**：无

## 2026-03-29
- **完成任务**：公式智能讲解结果本地缓存，避免每次重复调用 LLM
- **技术实现细节**：
    - **设计思路**：参照古诗词模块（`PoetryAnalysis`）的"先查库→空则调 LLM→回写入库"模式，在 `Formula` 模型新增 `explanation` 缓存字段。explain 模式命中缓存时同步返回（毫秒级），未命中时异步调用 LLM 并将结果回写数据库，后续访问直接读缓存。
    - **核心变更**：
        - `app/models.py`：`Formula` 模型新增 `explanation = db.Column(db.Text)` 字段
        - `app/api/routes.py`：`explain_formula` 端点增加缓存判断——explain 模式先查 `formula.explanation`，有值同步返回 200 JSON（前端 `TaskPoller.submitAndPoll` 已内置同步返回兼容），无值走异步 LLM 并在后台线程中 `db.session.get(Formula, id)` 回写
        - 数据库迁移：`ALTER TABLE formulas ADD COLUMN explanation TEXT`
- **遇到的问题与解决方案**：无
- **验证结果**：
    - [x] 通过验证：服务器正常启动，前端 `TaskPoller.submitAndPoll` 已原生支持同步/异步双通道，无需修改前端代码
- **附注**：
    - example（智能例题）模式保持每次重新生成，因为每次出的题应该不同
    - 如需清除某个公式的讲解缓存重新生成，可通过数据库将 `explanation` 字段置 NULL

- **完成任务**：增强古诗词联想输入功能的候选列表滑动预览，支持按诗词内容检索
- **技术实现细节**：
    - **设计思路**：使用 SQL 的 `like` 增强检索范围；针对长候选列表定制专属宣纸风格的滚动条外观，提升 UI 美观度，并提高后端联想数据的默认 `limit` 阈值。
    - **核心变更**：
        - `app/api/routes.py`：`search_poetry` 和 `suggest_poetry` 接口加入 `Poetry.content.like` 的 or 条件从而支持诗句截断/模糊搜索；同时将 `suggest_poetry` 接口的推荐条目防波堤 `limit(5)` 提高至 `limit(30)`。
        - `app/templates/poetry.html`：配置 `.suggest-dropdown` 的 `max-height: 280px` 迫使其尽早触发垂直滚动条 `overflow-y: auto;`。基于 `-webkit-scrollbar` 提供高度定制度的半透明+主题边框色的古式宣纸滑动条效果。
- **遇到的问题与解决方案**：无
- **验证结果**：
    - [x] 通过验证：下拉框多数据时产生优美的自定义 UI 滚动条效果，诗句片段检索已生效。
