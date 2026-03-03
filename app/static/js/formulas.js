/**
 * 公式手册逻辑模块 (Clean UI + MathJax 3)
 */
const FormulaManager = {
    state: {
        category: '',
        grade: '', 
        keyword: '',
        page: 1,
        perPage: 12,
        hasMore: true,
        isLoading: false,
        isSemantic: false,
        modal: null
    },

    init() {
        this.loadFormulas();
        this.initModal();
        this.initGeminiSearch();
    },

    initModal() {
        const el = document.getElementById('detailModal');
        if (el) {
            this.state.modal = new bootstrap.Modal(el);
        }
    },
    
    // 初始化 Gemini 搜索框组件
    initGeminiSearch() {
        if (typeof GeminiSearch !== 'undefined') {
            GeminiSearch.init({
                inputId: 'searchInput',
                aiToggleId: 'geminiAiToggle',
                onSearch: (query, isAIMode) => {
                    this.state.keyword = query;
                    this.state.isSemantic = isAIMode;
                    this.state.page = 1;
                    this.state.hasMore = true;
                    this.loadFormulas(true);
                }
            });
            
            // AI 按钮点击时同步状态
            const aiBtn = document.getElementById('geminiAiToggle');
            if (aiBtn) {
                aiBtn.addEventListener('click', () => {
                    // GeminiSearch 内部会 toggle，我们同步读取
                    setTimeout(() => {
                        this.state.isSemantic = GeminiSearch.isAIMode;
                        this.search();
                    }, 50);
                });
            }
        }
    },

    // 切换分类
    setCategory(cat) {
        if (this.state.category === cat) return;
        this.state.category = cat;
        this.state.page = 1;
        this.state.hasMore = true;
        // 保持语义搜索状态，不重置 isSemantic
        
        // 更新 Tab 样式 
        document.querySelectorAll('#formulaTabs .nav-link').forEach(btn => btn.classList.remove('active'));
        const tabId = cat === '' ? 'tab-all' : 
                      cat === '数学' ? 'tab-math' :
                      cat === '物理' ? 'tab-physics' : 'tab-chemistry';
        document.getElementById(tabId)?.classList.add('active');

        this.loadFormulas(true);
    },

    // 切换学段 
    setGrade(g) {
        if (this.state.grade === g) return;
        this.state.grade = g;
        this.state.page = 1;
        this.state.hasMore = true;

        // 更新 Chips 样式
        const gradeMap = {'': 'grade-all', '小学': 'grade-primary', '初中': 'grade-junior', '高中': 'grade-high', '大学': 'grade-univ'};
        
        // 重置所有按钮样式
        Object.values(gradeMap).forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.classList.remove('btn-secondary', 'active', 'text-white');
                btn.classList.add('btn-outline-secondary');
            }
        });

        // 激活当前按钮
        const activeId = gradeMap[g];
        const activeBtn = document.getElementById(activeId);
        if (activeBtn) {
            activeBtn.classList.remove('btn-outline-secondary');
            activeBtn.classList.add('btn-secondary', 'active', 'text-white');
        }

        this.loadFormulas(true);
    },

    // 搜索
    search() {
        const val = document.getElementById('searchInput').value.trim();
        this.state.keyword = val;
        this.state.page = 1;
        this.state.hasMore = true;
        this.loadFormulas(true);
    },

    // 加载数据
    async loadFormulas(reset = false) {
        if (this.state.isLoading) return;
        const container = document.getElementById('formulaList');
        const loadMoreBtn = document.getElementById('loadMoreContainer');
        
        if (reset) {
            container.innerHTML = '<div class="loading-spinner"><div class="spinner-border text-primary"></div></div>';
            loadMoreBtn.style.display = 'none';
        }

        this.state.isLoading = true;

        try {
            let data;
            // 判断是用语义搜索还是普通列表
            if (this.state.isSemantic && this.state.keyword) {
                const res = await fetch('/api/formulas/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        query: this.state.keyword,
                        category: this.state.category,
                        grade: this.state.grade
                    })
                });
                const json = await res.json();
                // 语义搜索接口返回结构略有不同，是一次性返回所有结果
                data = {
                    data: json.data || [],
                    total: (json.data || []).length,
                    pages: 1
                };
                this.state.hasMore = false; // 语义搜索不仅分页
            } else {
                const params = new URLSearchParams({
                    page: this.state.page,
                    per_page: this.state.perPage,
                    category: this.state.category,
                    grade: this.state.grade, // 新增参数
                    keyword: this.state.keyword
                });
                const res = await fetch(`/api/formulas?${params}`);
                data = await res.json();
                this.state.hasMore = this.state.page < data.pages;
            }

            if (reset) container.innerHTML = '';

            if (!data.data || data.data.length === 0) {
                if (reset) container.innerHTML = '<div class="text-center text-muted py-5">暂无相关公式</div>';
            } else {
                this.renderList(data.data);
            }

            // 更新加载更多按钮
            loadMoreBtn.style.display = this.state.hasMore ? 'block' : 'none';

        } catch (e) {
            console.error(e);
            if (reset) container.innerHTML = '<div class="text-center text-danger py-5">加载失败，请重试</div>';
        } finally {
            this.state.isLoading = false;
        }
    },

    loadMore() {
        if (!this.state.hasMore) return;
        this.state.page++;
        this.loadFormulas(false);
    },

    // 清洗 LaTeX 字符串 
    cleanLatex(str) {
        if (!str) return '';
        return str.replace(/\\\\/g, '\\');
    },

    // 渲染列表
    renderList(formulas) {
        const container = document.getElementById('formulaList');
        
        const html = formulas.map(f => {
            const displayLatex = this.cleanLatex(f.latex || f.formula);
            return `
            <div class="col-md-6 col-lg-4 animate__animated animate__fadeIn">
                <div class="card formula-card h-100 border-0 shadow-sm p-4" onclick="FormulaManager.showDetail(${f.id})">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <span class="badge bg-light text-dark border">${f.category || '通用'}</span>
                        ${f.score ? `<span class="badge bg-success-subtle text-success">匹配 ${(f.score*100).toFixed(0)}%</span>` : ''}
                    </div>
                    
                    <h5 class="fw-bold mb-3 text-center text-dark">${f.name}</h5>
                    
                    <div class="formula-preview my-3 text-center">
                        $${displayLatex}$
                    </div>
                    
                    <div class="mt-auto text-center">
                        <small class="text-primary fw-bold">查看详情 <i class="fas fa-arrow-right ms-1"></i></small>
                    </div>
                </div>
            </div>
        `}).join('');

        container.insertAdjacentHTML('beforeend', html);

        // 触发 MathJax 渲染
        if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
            MathJax.typesetPromise([container]).catch((err) => console.log('MathJax error:', err));
        }
    },

    // 显示详情
    async showDetail(id) {
        try {
            const res = await fetch(`/api/formulas/${id}`);
            const json = await res.json();
            
            if (json.success) {
                const f = json.data;
                document.getElementById('detailTitle').innerText = f.name;
                document.getElementById('detailCategory').innerText = f.category || '数学';
                document.getElementById('detailGrade').innerText = f.grade || '通用';
                const tagsContainer = document.getElementById('detailCode'); // ID 保持不变，内容变更
                if (f.tags && f.tags.length > 0) {
                   tagsContainer.innerHTML = f.tags.map(t => 
                       `<span class="badge bg-info-subtle text-info-emphasis me-1 border border-info-subtle">${t}</span>`
                   ).join('');
                } else {
                    tagsContainer.innerText = '';
                }
                
                //  动态设置视频链接
                const videoBtn = document.getElementById('videoLinkBtn');
                if (videoBtn) {
                     // 默认策略：跳转到 Bilibili 搜索该公式
                     const searchQuery = encodeURIComponent(f.name + ' 公式讲解');
                     videoBtn.href = `https://search.bilibili.com/all?keyword=${searchQuery}`;
                }

                // 渲染 LaTeX 容器
                const detailLatex = this.cleanLatex(f.latex || f.formula);
                const latexContainer = document.getElementById('detailLatex');
                latexContainer.innerText = `$$${detailLatex}$$`;
                
                // 变量
                const varsHtml = (f.variables || []).map(v => `
                    <div class="d-flex justify-content-between border-bottom py-2">
                        <span class="fw-bold text-primary font-monospace">$${this.cleanLatex(v.name)}$</span>
                        <span class="text-muted">${v.description || ''}</span>
                    </div>
                `).join('');
                document.getElementById('detailVars').innerHTML = varsHtml || '<span class="text-muted small">无变量说明</span>';

                document.getElementById('detailConditions').innerText = f.conditions || '无特殊条件';
                document.getElementById('detailNotes').innerText = f.derivation || f.notes || '暂无推导过程';

                this.state.modal.show();

                // 记录当前 ID
                this.state.currentFormulaId = id;
                
                // 重置 Tab 和 AI 内容
                const firstTabEl = document.querySelector('#detailTabs button:first-child');
                if(firstTabEl) new bootstrap.Tab(firstTabEl).show();
                
                document.getElementById('aiResponseArea').innerHTML = `
                    <div class="text-muted text-center py-4">
                        <i class="fas fa-robot fa-2x mb-2 text-secondary opacity-50"></i>
                        <p>点击上方按钮，帮你深入理解</p>
                    </div>
                `;

                // 渲染 Modal 内容
                if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
                    // 稍微延迟一下以等待 Modal 动画
                    setTimeout(() => {
                        MathJax.typesetPromise([document.getElementById('detailModal')]);
                    }, 200);
                }
            }
        } catch (e) {
            console.error(e);
            alert('获取详情失败');
        }
    },

    // AI 助手交互
    async askAI(type) {
        if (!this.state.currentFormulaId) return;
        
        const area = document.getElementById('aiResponseArea');
        area.innerHTML = `
            <div class="d-flex justify-content-center align-items-center py-5">
                <div class="spinner-border text-primary me-3" role="status"></div>
                <span class="text-primary fw-bold">正在讲解中...</span>
            </div>
        `;
        
        try {
            const res = await fetch('/api/formulas/explain', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    id: this.state.currentFormulaId,
                    type: type
                })
            });
            const json = await res.json();
            
            if (json.success) {
                let htmlContent = '';
                
                if (type === 'explain') {
                    // 解析模式：Markdown 渲染
                    if (window.marked) {
                        htmlContent = marked.parse(json.data);
                    } else {
                        htmlContent = json.data; // 降级处理
                    }
                } else if (type === 'example') {
                    // 例题模式：结构化展示
                    const q = json.data;
                    const optsHtml = (q.options || []).map(o => `<div class="p-2 border rounded mb-2 bg-white">${o}</div>`).join('');
                    
                    htmlContent = `
                        <div class="card border-success border-opacity-25 mb-3">
                            <div class="card-header bg-success-subtle text-success fw-bold">
                                <i class="fas fa-file-alt me-2"></i> 生成例题 (已入库)
                            </div>
                            <div class="card-body">
                                <h6 class="card-title fw-bold mb-3">${q.question}</h6>
                                <div class="mb-3">${optsHtml}</div>
                                
                                <div class="alert alert-light border">
                                    <strong>✅ 答案：</strong> ${q.answer}
                                </div>
                                <div class="small text-muted">
                                    <strong>💡 解析：</strong> ${q.reason}
                                </div>
                            </div>
                        </div>
                    `;
                }
                
                area.innerHTML = htmlContent;
                
                // 渲染公式
                if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
                    MathJax.typesetPromise([area]);
                }
            } else {
                area.innerHTML = `<div class="alert alert-danger">生成失败: ${json.message}</div>`;
            }
        } catch(e) {
            area.innerHTML = `<div class="alert alert-danger">网络错误: ${e.message}</div>`;
        }
    },

    copyLatex() {
        const latex = document.getElementById('detailLatex').innerText.replace(/\$\$/g, '');
        navigator.clipboard.writeText(latex).then(() => {
            alert('LaTeX 代码已复制！');
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    FormulaManager.init();
});
