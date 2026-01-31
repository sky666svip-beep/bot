---
description: # Project basic rule
---

## 前端规则
1. 前端核心基准为index.html，所有前端内容的新增、迭代、拓展均以该文件为基础核心，不得脱离其建立独立的前端基础体系；
2. 新增的所有前端独立页面（如各类功能页、详情页、子模块页等），必须与index.html建立明确的关联关系，禁止无关联的孤立页面开发；
3. 独立页面优先复用index.html中引入的 style.css 、JS、字体、图标等公共资源，减少重复引入；独立页面需包含与index.html的双向 / 单向跳转入口。

### 项目文件结构
d:\Projects\choicebot\
├── run.py                 # 项目启动入口 (Flask App)
├── advanced_import.py     # 数据导入脚本 (清洗 + 向量化)
├── init_db.py             # 数据库初始化脚本
├── seed.py                # 种子数据生成脚本
├── stopwords.txt          # 停用词表 (用于 NLP 清洗)
│
├── app\                   # 核心应用源码
│   ├── __init__.py        # Flask App 工厂函数 & 配置
│   ├── config.py          # 项目配置文件
│   ├── extensions.py      # 第三方扩展初始化 (db 等)
│   ├── models.py          # 数据库模型定义 (QuestionBank, UserHistory)
│   │
│   ├── api\               # API路由层
│   │   └── routes.py      # 核心业务逻辑路由 (搜索、历史、上传等)
│   │
│   ├── services\          # 核心服务层 (Backend Logic)
│   │   ├── nlp_service.py     # NLP 引擎 (Qwen 模型, 向量索引, 双路召回)
│   │   ├── answer_engine.py   # 解题 Pipeline 编排
│   │   └── llm_service.py     # 其他 LLM 服务 (视觉 OCR, 作文批改等)
│   │
│   ├── templates\         # 前端 HTML 模板
│   │   ├── index.html         # 首页 (搜题主界面)
│   │   ├── history.html       # 历史记录页
│   │   ├── formulas.html      # 公式手册页
│   │   ├── calculator.html    # 计算器页
│   │   ├── essay.html         # 作文批改页
│   │   └── study_plan.html    # 学习计划页
│   │
│   └── static\            # 静态资源
│       ├── css/             # 样式表
│       ├── js/              # 前端 JS 逻辑 (search-engine.js 等)
│       └── ...
│
├── data\                  # 原始题库数据文件夹 (如 Excel/CSV)
├── instance\              # 运行时生成的文件 (SQLite db, uploads)
└── model_cache_qwen\      # 本地 LLM 模型缓存目录