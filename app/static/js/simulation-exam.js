/**
 * simulation-exam.js
 * 处理模拟考试的 前端逻辑
 */

const ExamApp = {
    currentQuestions: [],
    
    init() {
        console.log("ExamApp Init");
        this.bindEvents();
    },
    
    bindEvents() {
        const form = document.getElementById('examForm');
        if (form) {
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.generateExam();
            });
        }
    },
    
    // 1. 生成试卷
    async generateExam() {
        const subject = document.getElementById('subject').value;
        const grade = document.getElementById('grade').value;
        const keypoint = document.getElementById('keypoint').value;
        const count = parseInt(document.getElementById('count').value);
        
        // 获取选中的题型
        const types = [];
        if(document.getElementById('type1').checked) types.push('单选题');
        if(document.getElementById('type2').checked) types.push('判断题');
        if(document.getElementById('type3').checked) types.push('填空题');
        if(document.getElementById('type4').checked) types.push('简答题');
        
        if (types.length === 0) {
            alert("请至少选择一种题型");
            return;
        }

        // 显示 Loading
        document.getElementById('loadingMask').style.display = 'flex';
        
        try {
            const data = await TaskPoller.submitAndPoll('/api/simulation/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject, grade, keypoint, count, types })
            });
            
            if (data.success) {
                this.currentQuestions = data.questions;
                this.renderQuestions(data.questions);
                document.getElementById('filterSection').style.display = 'none';
                document.getElementById('examArea').style.display = 'block';
                window.scrollTo(0, 0);
            } else {
                alert("生成失败: " + data.message);
            }
            
        } catch (e) {
            console.error(e);
            alert("请求出错，请检查网络");
        } finally {
            document.getElementById('loadingMask').style.display = 'none';
        }
    },
    
    // 2. 渲染题目
    renderQuestions(questions) {
        const container = document.getElementById('questionsContainer');
        container.innerHTML = '';
        
        questions.forEach((q, index) => {
            // 给每个题目分配一个临时 ID 用于提交时对应
            q.temp_id = 'q_' + index;
            
            const card = document.createElement('div');
            card.className = 'card main-card mb-4 question-card';
            card.innerHTML = `
                <div class="card-body p-4">
                    <h5 class="card-title fw-bold mb-3">
                        <span class="badge bg-primary me-2">${index + 1}</span>
                        <span class="badge bg-info-subtle text-info me-2">${q.type || '题目'}</span>
                        ${q.question}
                    </h5>
                    
                    <div class="options-area mt-3" id="opts-${index}">
                        ${this.renderOptions(q, index)}
                    </div>
                </div>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        // 渲染完成后触发 MathJax
        if (window.MathJax) {
            // 兼容 MathJax 3.x Promsie 和 2.x Hub
            if (MathJax.typesetPromise) {
                MathJax.typesetPromise([container]).catch(err => console.log('MathJax error:', err));
            } else if (MathJax.Hub) {
                MathJax.Hub.Queue(["Typeset", MathJax.Hub, container]);
            }
        }
    },
    
    renderOptions(q, index) {
        // 单选题/判断题 -> 显示选项
        if (q.type === '单选题' || q.type === '判断题') {
            const opts = q.options || (q.type === '判断题' ? ['A. 正确', 'B. 错误'] : []);
            
            // 缓存 UI 使用的选项列表，供 selectOption 使用
            q.ui_options = opts; 

            return opts.map((opt, i) => {
                // 分离 "A. 内容" 为 Label 和 Content
                let label = "";
                let content = opt;
                // 匹配 A. 或 A、 或 A (space)
                const match = opt.match(/^([A-Z])[\.\、\s](.*)/); 
                if (match) {
                    label = match[1] + ".";
                    content = match[2];
                }
                // 判断是否是简短的判断题
                else if (opt.includes("正确") || opt.includes("错误")) {
                    label = String.fromCharCode(65 + i) + "."; // 生成 A. B.
                }

                return `
                <div class="card option-card mb-2 p-3 d-flex flex-row align-items-center" onclick="ExamApp.selectOption(${index}, ${i}, this)">
                    ${label ? `<span class="fw-bold me-3 fs-5 text-primary">${label}</span>` : ''}
                    <div class="flex-grow-1">${content}</div>
                </div>
            `}).join('');
        } 
        // 填空题/简答题 -> 输入框
        else {
            const isShortAnswer = q.type === '简答题';
            return `
                ${isShortAnswer ? 
                    `<textarea class="form-control" rows="4" placeholder="请在此输入简答内容..." onchange="ExamApp.recordInput(${index}, this.value)"></textarea>` : 
                    `<input type="text" class="form-control" placeholder="请输入答案..." onchange="ExamApp.recordInput(${index}, this.value)">`
                }
            `;
        }
    },
    
    escapeHtml(str) {
        if (!str) return '';
        return str.replace(/'/g, "&#39;").replace(/"/g, "&quot;");
    },
    
    // 3. 用户作答交互
    // 【关键修改】第二个参数改为 optIndex
    selectOption(qIndex, optIndex, el) {
        // 根据索引获取原始选项内容
        const q = this.currentQuestions[qIndex];
        let optValue = "";
        
        if (q.ui_options && q.ui_options[optIndex]) {
            optValue = q.ui_options[optIndex];
        } else {
            console.error("Option not found or UI options missing");
            return;
        }

        this.currentQuestions[qIndex].my_answer_raw = optValue;
        
        // 提取 A, B, C...
        let val = optValue;
        const match = optValue.match(/^([A-Z])[\.\、\s]/); // 匹配宽松一点
        if (match) val = match[1]; 
        else if (optValue.includes("正确")) val = "正确";
        else if (optValue.includes("错误")) val = "错误";
        
        this.currentQuestions[qIndex].my_answer = val;
        
        // UI 更新：先移除该题所有选中样式
        const parent = document.getElementById(`opts-${qIndex}`);
        parent.querySelectorAll('.option-card').forEach(c => c.classList.remove('selected'));
        el.classList.add('selected');
    },
    
    recordInput(qIndex, val) {
        this.currentQuestions[qIndex].my_answer = val.trim();
        this.currentQuestions[qIndex].my_answer_raw = val.trim();
    },
    
    // 4. 提交判卷
    async submitExam() {
        if (!confirm("确定要提交答案吗？")) return;
        
        // --- 1. 本地判卷 ---
        let score = 0;
        const total = this.currentQuestions.length;
        const results = [];
        
        this.currentQuestions.forEach(q => {
            const myAns = q.my_answer || "";
            const correctAns = q.answer || "";
            let isCorrect = false;

            if (q.type === '简答题') {
                isCorrect = myAns.length > 0;
            } else {
                // 客观题比对
                let cleanCorrect = correctAns.toString().trim().toUpperCase();
                let cleanMy = myAns.toString().trim().toUpperCase();

                // 针对单选题/判断题，尝试从参考答案中提取 "A", "B" 等前缀
                if (q.type === '单选题' || q.type === '判断题') {
                    const match = cleanCorrect.match(/^([A-Z])[\.\、\s]/);
                    if (match) {
                        cleanCorrect = match[1];
                    } 
                    // 针对判断题：如果 AI 只返回了中文 "正确" / "错误"，转换成 A / B
                    else if (q.type === '判断题') {
                        if (cleanCorrect.includes('正确')) cleanCorrect = 'A';
                        else if (cleanCorrect.includes('错误')) cleanCorrect = 'B';
                    }
                }

                isCorrect = cleanMy === cleanCorrect || 
                            (q.type === '填空题' && correctAns.includes(myAns));
            }
            
            if (isCorrect) score++;
            
            results.push({
                ...q,
                is_correct: isCorrect,
                category: document.getElementById('subject').value 
            });
        });
        
        const finalScore = Math.round((score / total) * 100);
        
        // --- 2. 提交到后端保存 ---
        try {
            const data = await TaskPoller.submitAndPoll('/api/simulation/submit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ results })
            });
            
            if (data.success) {
                const idMap = {};
                data.saved_ids.forEach(item => {
                    idMap[item.temp_id] = item.db_id;
                });
                
                results.forEach(r => {
                    r.db_id = idMap[r.temp_id];
                });

                this.showResult(finalScore, results);
                if (typeof Notebook !== 'undefined') Notebook.refreshAll();

            } else {
                alert("保存成绩失败，但你可以查看本次结果。");
                this.showResult(finalScore, results);
            }
        } catch (e) {
            console.error(e);
            alert("提交失败，请检查网络");
        }
    },
    
    // 5. 展示结果与解析
    showResult(score, results) {
        document.getElementById('examArea').style.display = 'none';
        document.getElementById('resultArea').style.display = 'block';
        window.scrollTo(0, 0);
        
        const scoreEl = document.getElementById('finalScore');
        this.animateValue(scoreEl, 0, score, 1000);
        
        const commentEl = document.getElementById('scoreComment');
        if (score >= 90) commentEl.innerText = "太棒了！简直是学霸！🎉";
        else if (score >= 60) commentEl.innerText = "成绩合格，还需要继续稳固哦！👍";
        else commentEl.innerText = "还需努力，建议加入错题本重点复习！💪";
        
        const container = document.getElementById('analysisContainer');
        container.innerHTML = results.map((r, i) => {
            const isShortAnswer = r.type === '简答题';
            const statusColor = r.is_correct ? 'success' : 'danger';
            const statusIcon = r.is_correct ? '✅' : '❌';
            const statusText = isShortAnswer ? '请自评 📝' : (r.is_correct ? '回答正确 ✅' : '回答错误 ❌');
             // 简答题总是显示加入错题本按钮，方便用户收藏
            const showMistakeBtn = !r.is_correct || isShortAnswer; 

            return `
            <div class="card mb-3 border-${isShortAnswer ? 'warning' : statusColor}">
                <div class="card-header bg-${isShortAnswer ? 'warning' : statusColor}-subtle">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="fw-bold text-${isShortAnswer ? 'dark' : statusColor}">
                            第${i+1}题 (${r.type || '未知'})：${statusText}
                        </span>
                        
                        ${showMistakeBtn ? `
                            <button id="mis-btn-${r.db_id}" class="btn btn-sm btn-outline-danger" 
                                onclick="ExamApp.toggleMistake(this, ${r.db_id})">
                                <i class="far fa-star"></i> 加入错题本
                            </button>
                        ` : ''}
                    </div>
                </div>
                <div class="card-body">
                    <p class="card-text fw-bold">${r.question}</p>
                    <div class="row g-2 mb-2">
                        <div class="col-md-6">
                            <div class="p-2 border rounded">
                                <small class="text-muted d-block">你的答案</small>
                                <span class="text-dark fw-bold">
                                    ${r.my_answer_raw || '未作答'}
                                </span>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="p-2 border rounded bg-success-subtle">
                                <small class="text-secondary d-block">参考答案</small>
                                <span class="text-success fw-bold">${r.answer}</span>
                            </div>
                        </div>
                    </div>
                    <div class="alert alert-secondary mb-0 p-2" style="font-size: 0.9rem;">
                        <strong><i class="fas fa-search me-1"></i>解析：</strong>${r.reason}
                    </div>
                </div>
            </div>
            `
        }).join('');

        // MathJax 渲染
        if (window.MathJax) {
            MathJax.typesetPromise([container]).catch(err => console.log(err));
        }
    },
    
    // 复用 toggle 逻辑
    async toggleMistake(btn, id) {
        if (typeof Notebook !== 'undefined') {
            await Notebook.toggleStatus(id, 'mistake');
        }
    },
    
    animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            obj.innerHTML = Math.floor(progress * (end - start) + start);
            if (progress < 1) {
                window.requestAnimationFrame(step);
            }
        };
        window.requestAnimationFrame(step);
    }
};

// 启动
document.addEventListener('DOMContentLoaded', () => {
    ExamApp.init();
});
