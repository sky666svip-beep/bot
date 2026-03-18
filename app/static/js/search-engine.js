/**
 * SearchEngine 模块：负责搜题核心逻辑
 */
const SearchEngine = {
    // 1. 文本搜题主逻辑
    async processAndSolve() {
        const rawText = document.getElementById('rawText').value.trim();
        if (!rawText) return alert("请输入题目内容或上传图片");
        this.updateStatus(true, "正在智能检索中...");
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: rawText })
            });
            const result = await response.json();

            if (result.success) {
                // 渲染结果
                this.displayResult(result.data);
                // 如果仪表盘存在则刷新
                if (typeof Dashboard !== 'undefined') Dashboard.loadData();
            } else {
                alert("搜索失败: " + result.message);
            }
        } catch (error) {
            console.error("搜索异常:", error);
            alert("系统繁忙，请稍后再试");
        } finally {
            this.updateStatus(false);
        }
    },

    // 2. 渲染搜索结果
    displayResult(data) {
        const resultArea = document.getElementById('resultArea');
        const targetAnswer = document.getElementById('targetAnswer'); // 答案容器
        const explanation = document.getElementById('explanation');   // 解析容器
        const sourceBadge = document.getElementById('sourceBadge');

        if (!resultArea || !targetAnswer) return;

        // 1. 显示结果区域
        resultArea.style.display = 'block';

        // 2.  Markdown 与 MathJax 混合解析
        const renderMarkdownWithMath = (text) => {
            if (!text) return "";
            let t = String(text).trim();
            // 启发式判断裸公式
            if (!t.startsWith('$') && !t.startsWith('\\[') && !t.startsWith('\\(') && !t.includes('$')) {
                let hasMathFeatures = t.includes('\\') || t.includes('^');
                if (hasMathFeatures) {
                    let chineseCount = (t.match(/[\u4e00-\u9fa5]/g) || []).length;
                    if (chineseCount <= 2 || chineseCount / t.length < 0.15) {
                        t = '$$' + t + '$$';
                    } else {
                        t = t.replace(/((?:[a-zA-Z0-9_.=+\-*/()]+)?(?:\\[a-zA-Z]+(?:\{[^}]*\})*|[a-zA-Z0-9_]+\^[a-zA-Z0-9_{}.+\-]+)(?:[a-zA-Z0-9_.=+\-*/(){}\\^]*(?:\\[a-zA-Z]+(?:\{[^}]*\})*|[a-zA-Z0-9_]+\^[a-zA-Z0-9_{}.+\-]+))*(?:[a-zA-Z0-9_.=+\-*/()]*)?)/g, (match) => {
                            if (/\\[a-zA-Z]|\^/.test(match)) return '$' + match + '$';
                            return match;
                        });
                    }
                }
            }
            const mathBlocks = [];
            const mathRegex = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$[^$\n]*?\$)/g;
            let processedText = t.replace(mathRegex, (match) => {
                mathBlocks.push(match.replace(/</g, '&lt;').replace(/>/g, '&gt;'));
                return `@@MATH_BLOCK_${mathBlocks.length - 1}@@`;
            });
            let html = typeof marked !== 'undefined' ? marked.parse(processedText, { breaks: true }) : processedText;
            
            if (html.startsWith('<p>') && html.endsWith('</p>\n')) {
                const count = (html.match(/<p>/g) || []).length;
                if (count === 1) html = html.substring(3, html.length - 5);
            }
            
            return html.replace(/@@MATH_BLOCK_(\d+)@@/g, (match, index) => mathBlocks[index]);
        };

        if (typeof marked !== 'undefined') {
            targetAnswer.innerHTML = renderMarkdownWithMath(data.answer || "无答案内容");
            explanation.innerHTML = renderMarkdownWithMath(data.reason || "暂无详细解析");
        } else {
            targetAnswer.innerText = data.answer;
            explanation.innerText = data.reason;
        }

        // 2. 学科显示
        const category = data.category || "其他";
        const source = data.source || "智能检索";
        sourceBadge.innerText = `${category} (${source})`;
        sourceBadge.className = data.source === '本地匹配' ? 'badge bg-success' : 'badge bg-primary';

        // 3. 错题本按钮逻辑
        // 直接通过 index.html 里定义的 ID 获取按钮，确保能找到
        const starBtn = document.getElementById('toggleMistakeBtn');
        if (starBtn) {
            // 给按钮赋予一个带 ID 的标识，方便 notebook.js 操作它
            starBtn.id = `mis-btn-${data.id}`;

            // 绑定点击事件：调用 Notebook.toggleStatus
            starBtn.onclick = () => Notebook.toggleStatus(data.id, 'mistake');

            // 初始化样式：如果是错题显示红色实心，否则显示灰色空心
            if (data.is_mistake) {
                starBtn.className = "btn btn-sm btn-danger ms-2";
                starBtn.innerHTML = '<i class="fas fa-star"></i>';
                starBtn.title = "已加入错题本 (点击移除)";
            } else {
                starBtn.className = "btn btn-sm btn-outline-secondary ms-2";
                starBtn.innerHTML = '<i class="far fa-star"></i>';
                starBtn.title = "加入错题本";
            }
        }

        // 4. 通知 MathJax 重新渲染数学公式
        if (window.MathJax) {
            MathJax.typesetPromise([resultArea]).catch((err) => console.dir(err));
        }
    },

    // 3. 图片搜题处理
    async handleImageUpload() {
        const fileInput = document.getElementById('imageUpload');
        const file = fileInput ? fileInput.files[0] : null;
        if (!file) {
            console.error("错误：没有检测到已选择的文件");
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        this.updateStatus(true, "正在识别图片题目，请稍候...");

        try {
            const response = await fetch('/api/solve-image', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            const finalData = result.success ? result.data : result;

            if (finalData && finalData.answer) {
                const resultArea = document.getElementById('resultArea');
                if (resultArea) resultArea.style.display = 'block';

                this.displayResult({
                    id: finalData.id || 0,
                    answer: finalData.answer,
                    reason: finalData.reason || "暂无详细解析",
                    category: finalData.category || "其他",
                    source: finalData.source || "图片识别",
                    is_mistake: finalData.is_mistake || false // 确保传递错题状态
                });

                if (resultArea) resultArea.scrollIntoView({ behavior: 'smooth' });
                if (typeof Dashboard !== 'undefined') Dashboard.loadData();
            } else {
                throw new Error(result.message || "后端未返回有效答案");
            }

        } catch (error) {
            console.error("❌ 流程异常:", error);
            if (error.message !== "识别失败") {
                 alert("识别出错了: " + error.message);
            }
        } finally {
            this.updateStatus(false);
            if (fileInput) fileInput.value = '';
        }
    },

    // 4. 文档解析处理 (PDF/DOCX)
    async handleDocUpload() {
        const fileInput = document.getElementById('docUpload');
        if (!fileInput || !fileInput.files.length) return;

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        this.updateStatus(true, `正在深度解析文档: ${file.name}...`);

        try {
            const response = await fetch('/api/upload-doc', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                document.getElementById('rawText').value = data.full_text;
                setTimeout(() => this.processAndSolve(), 800);
            } else {
                alert("文档解析失败: " + data.message);
            }
        } catch (error) {
            alert("文档服务异常");
        } finally {
            this.updateStatus(false);
            fileInput.value = '';
        }
    },

    // 状态更新辅助
    updateStatus(show, text = "") {
        const statusMsg = document.getElementById('statusMessage');
        const statusText = document.getElementById('statusText');
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) submitBtn.disabled = show;
        if (!statusMsg) return;

        if (show) {
            statusMsg.style.display = 'block';
            if (statusText) statusText.innerText = text;
            else statusMsg.innerText = text;
        } else {
            statusMsg.style.display = 'none';
        }
    },
};