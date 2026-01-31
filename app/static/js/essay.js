let currentMode = 'chinese';

function setMode(mode) {
    currentMode = mode;
    // 切换时清空结果或保留输入看你需求
    const input = document.getElementById('essayInput');
    input.placeholder = mode === 'chinese' ? "请输入语文作文..." : "Please paste your English essay here...";

    // 切换模式时，清空之前的校验警告（如果有的话）
    input.classList.remove('is-invalid');
}

// 1. 文件上传处理 (复用 /upload-doc 接口)
document.getElementById('fileInput').addEventListener('change', async function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    showLoadingInput(true);
    try {
        const res = await fetch('/upload-doc', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            document.getElementById('essayInput').value = data.full_text;
        } else {
            alert('解析失败: ' + data.message);
        }
    } catch (err) {
        alert('上传出错');
    } finally {
        showLoadingInput(false);
        e.target.value = ''; // 重置
    }
});

// 2. 提交批改 (新增语言检测逻辑)
async function submitCorrection() {
    const inputEl = document.getElementById('essayInput');
    const text = inputEl.value.trim();

    if (!text) {
        alert('请输入作文内容');
        return;
    }

    // === 新增：语言匹配度检测 ===
    const hasChineseChar = /[\u4e00-\u9fa5]/.test(text);

    if (currentMode === 'chinese') {
        // 场景 A: 选了语文，但输入里没有一个汉字 (可能是纯英文)
        if (!hasChineseChar) {
            alert('⚠️ 语言模式不匹配\n\n当前是【语文作文】模式，但检测到您的输入似乎是英文。\n请切换到“英语作文”板块，或输入中文内容。');
            return; // 阻止提交
        }
    } else if (currentMode === 'english') {
        // 场景 B: 选了英语，但输入里包含汉字 (可能是纯中文或中英混杂)
        // 这里做一个简单的阈值判断，防止因为一两个标点符号误判，但通常英语作文不应包含汉字
        if (hasChineseChar) {
            alert('⚠️ 语言模式不匹配\n\n当前是【英语作文】模式，但检测到您的输入包含中文。\n请切换到“语文作文”板块，或移除中文内容。');
            return; // 阻止提交
        }
    }
    // ===========================

    // UI 状态切换
    document.getElementById('resultContent').classList.add('d-none');
    document.getElementById('emptyState').classList.add('d-none');
    document.getElementById('loading').classList.remove('d-none');
    document.getElementById('submitBtn').disabled = true;

    try {
        const res = await fetch('/api/essay/correct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, type: currentMode })
        });
        const data = await res.json();

        if (data.success) {
            renderResult(data.data);
        } else {
            alert(data.message);
        }
    } catch (err) {
        alert('请求失败: ' + err);
    } finally {
        document.getElementById('loading').classList.add('d-none');
        document.getElementById('submitBtn').disabled = false;
    }
}

// 3. 渲染结果 (全新样式适配版)
function renderResult(data) {
    const container = document.getElementById('resultContent');

    // 清空旧内容并显示容器
    container.innerHTML = '';
    container.classList.remove('d-none');

    // 判断评分等级对应的颜色类
    const scoreClass = getScoreColorClass(data.score);
    const scoreIcon = getScoreIcon(data.score);

    let html = '';

    if (currentMode === 'chinese') {
        // --- 语文模板 ---
        html = `
            <div class="score-badge-container">
                <div>
                    <span class="text-muted small d-block mb-1">综合等级</span>
                    <span class="score-value ${scoreClass}">${data.score}</span>
                </div>
                <i class="${scoreIcon} fa-3x ${scoreClass} opacity-25"></i>
            </div>
            
            <div class="sub-card">
                <div class="sub-title"><i class="fas fa-quote-left"></i> 老师总评</div>
                <p class="detail-text mb-0">${data.summary}</p>
            </div>

            <div class="sub-card">
                <div class="sub-title"><i class="fas fa-thumbs-up"></i> 作文亮点</div>
                <ul class="list-unstyled mb-0 detail-text">
                    ${data.highlights.map(h => `<li class="mb-2"><i class="fas fa-check-circle text-success me-2"></i>${h}</li>`).join('')}
                </ul>
            </div>

            <div class="sub-card">
                <div class="sub-title"><i class="fas fa-lightbulb"></i> 改进建议</div>
                <ul class="list-unstyled mb-0 detail-text">
                    ${data.suggestions.map(s => `<li class="mb-2"><i class="fas fa-arrow-circle-right text-warning me-2"></i>${s}</li>`).join('')}
                </ul>
            </div>
        `;
    } else {
        // --- 英语模板 ---
        html = `
             <div class="score-badge-container">
                <div>
                    <span class="text-muted small d-block mb-1">Overall Grade</span>
                    <span class="score-value ${scoreClass}">${data.score}</span>
                </div>
                <i class="${scoreIcon} fa-3x ${scoreClass} opacity-25"></i>
            </div>
            
            <div class="sub-card bg-light border-0">
                <div class="sub-title"><i class="fas fa-comment-dots"></i> Comment</div>
                <p class="detail-text fst-italic mb-0">"${data.comment}"</p>
            </div>

            <div class="sub-card">
                <div class="sub-title text-danger"><i class="fas fa-bug"></i> Corrections</div>
                ${data.corrections.length === 0 ? '<p class="text-success small"><i class="fas fa-check"></i> Perfect! No errors found.</p>' : ''}
                <div class="d-flex flex-column gap-3">
                    ${data.corrections.map(c => `
                        <div class="p-2 bg-white border rounded">
                            <div class="mb-1">
                                <span class="highlight-bad">${c.error}</span>
                                <i class="fas fa-arrow-right correction-arrow"></i>
                                <span class="highlight-good">${c.fix}</span>
                            </div>
                            <small class="text-muted d-block"><i class="fas fa-info-circle me-1"></i>${c.explanation}</small>
                        </div>
                    `).join('')}
                </div>
            </div>

            <div class="sub-card">
                <div class="sub-title text-info"><i class="fas fa-rocket"></i> Expression Boost</div>
                <div class="d-flex flex-column gap-3">
                    ${data.enhancements.map(e => `
                        <div class="p-2 bg-white border rounded">
                            <div class="text-muted small mb-1 text-decoration-line-through">${e.original}</div>
                            <div class="text-dark fw-bold"><i class="fas fa-magic text-info me-1"></i>${e.improved}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

// 辅助函数：获取评分颜色
function getScoreColorClass(score) {
    if (['优秀', 'A', 'A+', 'Excellent'].includes(score)) return 'score-A';
    if (['良好', 'B', 'Good'].includes(score)) return 'score-B';
    if (['中等', 'C', 'Medium'].includes(score)) return 'score-C';
    if (['及格', 'D', 'Pass'].includes(score)) return 'score-D';
    return 'score-F';
}
// 辅助函数：获取评分图标
function getScoreIcon(score) {
    if (['优秀', 'A', 'A+'].includes(score)) return 'fa-star';
    if (['良好', 'B'].includes(score)) return 'fa-thumbs-up';
    if (['不及格', 'F'].includes(score)) return 'fa-exclamation-triangle';
    return 'fa-clipboard-list';
}

const imgInput = document.getElementById('imgInput');
if (imgInput) {
    imgInput.addEventListener('change', async function(e) {
        console.log('【调试】1. 检测到图片文件选择');

        const file = e.target.files[0];
        if (!file) {
            console.log('【调试】用户取消了文件选择');
            return;
        }
        console.log('【调试】文件名:', file.name, '大小:', file.size);

        // 1. 锁定界面，显示加载中
        showLoadingInput(true);
        console.log('【调试】2. 界面已锁定，准备上传...');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/ocr-image', {
                method: 'POST',
                body: formData
            });

            if (!res.ok) {
                throw new Error(`HTTP 错误: ${res.status}`);
            }

            const data = await res.json();

            if (data.success) {
                // 3. 成功拿到文字，填入输入框
                const extractedText = data.text;

                const textArea = document.getElementById('essayInput');
                textArea.value = extractedText;

                // 自动调整高度 (可选)
                textArea.style.height = 'auto';
                textArea.style.height = textArea.scrollHeight + 'px';
            } else {
                alert('识别失败: ' + data.message);
            }

        } catch (err) {
            alert('上传出错: ' + err.message);
        } finally {
            // 4. 无论成功失败，都要恢复界面
            showLoadingInput(false);
            e.target.value = ''; // 清空 input，防止下次选同一张图不触发 change
        }
    });
} else {
    // console.error('【严重错误】找不到 id="imgInput" 的元素，请检查 HTML!');
}

function showLoadingInput(isLoading) {
    const input = document.getElementById('essayInput');
    if(isLoading) {
        input.value = "正在读取文件内容...";
        input.disabled = true;
    } else {
        input.disabled = false;
    }
}