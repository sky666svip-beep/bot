// static/js/notebook.js

const Notebook = {
    init() {
        console.log("Notebook 模块启动...");
        // 页面加载时自动刷新侧边栏
        this.refreshAll();
    },

    // 1. 加载侧边栏错题列表 (只展示，不含移除按钮)
    refreshAll: async function() {
        const container = document.getElementById('mistakeList');
        if (!container) return;

        try {
            const res = await fetch('/api/history-data?filter=mistake');
            const data = await res.json();

            // 过滤出 is_mistake 为 true 的记录
            const mistakes = data.filter(item => item.is_mistake);

            if (mistakes.length === 0) {
                container.innerHTML = '<div class="text-center mt-5 text-muted">目前还没有记录错题哦</div>';
                return;
            }

            // 渲染列表：去掉了移除按钮，保留了查看详情
            container.innerHTML = mistakes.map(item => `
                <div class="list-group-item border-bottom py-3">
                    <div class="d-flex justify-content-between align-items-start">
                        <span class="badge bg-danger-subtle text-danger mb-2">${item.category || '学科'}</span>
                        <small class="text-muted">${item.time || ''}</small>
                    </div>
                    <div class="fw-bold text-truncate-2 mb-2" style="font-size: 0.95rem;">${item.question}</div>
                    
                    <div class="d-flex justify-content-between align-items-center mt-2">
                        <button class="btn btn-sm btn-link p-0 text-decoration-none" 
                                onclick='Notebook.viewDetail(${JSON.stringify(item).replace(/'/g, "&#39;")})'>
                            <i class="fas fa-eye me-1"></i>查看详情
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (err) {
            console.error("加载错题本失败:", err);
            container.innerHTML = '<div class="text-center mt-5 text-danger">加载失败，请重试</div>';
        }
    },

    // 2. 状态切换函数：控制红/灰变色
    toggleStatus: async function(id, type) {
        try {
            const res = await fetch(`/api/history/${id}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type })
            });
            const data = await res.json();

            if (data.success) {
                // 找到搜题结果卡片上的那个按钮
                const btn = document.getElementById(`mis-btn-${id}`);

                if (btn) {
                    if (data.new_status) {
                        // === 变红 (加入错题) ===
                        btn.classList.remove('btn-outline-secondary');
                        btn.classList.add('btn-danger');
                        btn.innerHTML = '<i class="fas fa-star"></i>'; // 实心星
                        btn.title = "已加入错题本 (点击移除)";
                    } else {
                        // === 变灰 (移出错题) ===
                        btn.classList.remove('btn-danger');
                        btn.classList.add('btn-outline-secondary');
                        btn.innerHTML = '<i class="far fa-star"></i>'; // 空心星
                        btn.title = "加入错题本";
                    }
                }

                // 刷新侧边栏 (实时反映添加/移除结果)
                this.refreshAll();
            }
        } catch (err) {
            console.error("操作失败", err);
            alert("操作失败，请检查网络");
        }
    },

    // 3. 查看详情：直接展示已存数据，不再调用 AI
    viewDetail: function(item) {
        // 回填文字，只作为展示
        const textarea = document.getElementById('rawText');
        if (textarea) textarea.value = item.question;

        // 关闭侧边栏
        const drawerEl = document.getElementById('notebookDrawer');
        if (drawerEl) {
            const drawer = bootstrap.Offcanvas.getInstance(drawerEl);
            if(drawer) drawer.hide();
        }

        // 直接渲染结果，不再调用 processAndSolve
        if (typeof SearchEngine !== 'undefined') {
            // 构造符合 displayResult 格式的数据
            const displayData = {
                id: item.id,
                answer: item.answer || "暂无答案",
                reason: item.reason || "暂无解析",
                category: item.category || "其他",
                source: item.source || "错题本",
                is_mistake: item.is_mistake !== false // 默认为 true
            };
            
            SearchEngine.displayResult(displayData);
            
            // 滚动到结果区
            const resultArea = document.getElementById('resultArea');
            if (resultArea) {
                resultArea.style.display = 'block';
                resultArea.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    Notebook.init();
});