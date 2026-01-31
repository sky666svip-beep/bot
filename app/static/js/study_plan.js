const Planner = {
    currentPlan: [],

    init() {
        this.bindEvents();
        this.loadHistory();
        this.updateTimeDisplay();
    },

    bindEvents() {
        // 学科选择多选
        document.querySelectorAll('.tech-checkbox').forEach(el => {
            el.addEventListener('click', () => {
                el.classList.toggle('active');
            });
        });

        // 时间滑块
        document.getElementById('timeRange').addEventListener('input', (e) => {
            document.getElementById('timeDisplay').innerText = e.target.value + 'h';
        });
    },

    updateTimeDisplay() {
        const val = document.getElementById('timeRange').value;
        document.getElementById('timeDisplay').innerText = val + 'h';
    },

    // 收集表单数据
    getFormData() {
        const subjects = Array.from(document.querySelectorAll('.tech-checkbox.active'))
                              .map(el => el.dataset.val);

        return {
            grade: document.getElementById('gradeSelect').value,
            subjects: subjects.length ? subjects.join(',') : '全科',
            weakness: document.querySelector('input[name="weakness"]').value,
            startTime: document.getElementById('startTime').value,
            duration: document.getElementById('timeRange').value,
            goal: document.querySelector('select[name="goal"]').value
        };
    },

    // 核心：生成计划
    async generate() {
        const formData = this.getFormData();

        // UI 状态
        document.getElementById('loadingState').classList.remove('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        document.getElementById('resultArea').classList.add('d-none');

        try {
            const res = await fetch('/api/study-plan/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            const result = await res.json();

            if (result.success) {
                this.currentPlan = result.data.tasks;
                localStorage.setItem('choicebot_last_plan', JSON.stringify(result.data));
                this.render(result.data);
            } else {
                alert('生成失败: ' + result.message);
            }
        } catch (err) {
            console.error(err);
            alert('网络连接异常');
        } finally {
            document.getElementById('loadingState').classList.add('d-none');
        }
    },

    // 渲染页面
    render(data) {
        document.getElementById('resultArea').classList.remove('d-none');
        document.getElementById('aiAnalysis').innerText = data.analysis;

        this.renderTasks(data.tasks);
        this.renderCharts(data.tasks);
        this.updateProgress();
    },

    // 渲染任务列表
    renderTasks(tasks) {
        const container = document.getElementById('taskListContainer');
        container.innerHTML = tasks.map((task, index) => `
            <div class="task-item priority-${task.priority} bg-white shadow-sm mb-3 rounded border" id="task-${index}">
                <div class="d-flex align-items-center justify-content-between p-3">
                    <div class="d-flex align-items-center gap-3">
                        <div class="check-circle" onclick="Planner.toggleTask(${index})"></div>
                        <div>
                            <div class="fw-bold text-dark fs-5">${task.time_range} <span class="mx-2 text-muted">|</span> ${task.task}</div>
                            <div class="task-meta mt-1">
                                <span class="badge bg-light text-dark border">${task.subject}</span>
                                <span class="badge bg-light text-dark border">${task.type}</span>
                                <span class="badge bg-light text-dark border"><i class="far fa-clock me-1"></i>${task.duration}min</span>
                            </div>
                        </div>
                    </div>
                    <button class="btn btn-sm btn-link text-primary" onclick="Planner.showDetail('${task.method}')">
                        <i class="fas fa-info-circle"></i>
                    </button>
                </div>
            </div>
        `).join('');
    },

    toggleTask(index) {
        const el = document.getElementById(`task-${index}`);
        el.classList.toggle('completed');
        this.updateProgress();
    },

    updateProgress() {
        const total = document.querySelectorAll('.task-item').length;
        const done = document.querySelectorAll('.task-item.completed').length;
        const chart = echarts.init(document.getElementById('progressChart'));
        chart.setOption({
            series: [{
                type: 'pie',
                radius: ['70%', '90%'],
                label: { show: true, position: 'center', formatter: '{d}%', color: '#0d6efd', fontSize: 14, fontWeight: 'bold' },
                data: [
                    { value: done, itemStyle: { color: '#0d6efd' } },
                    { value: total - done, itemStyle: { color: '#e9ecef' } }
                ]
            }]
        });
    },

    renderCharts(tasks) {
        const subjectMap = {};
        tasks.forEach(t => subjectMap[t.subject] = (subjectMap[t.subject] || 0) + t.duration);
        const pieData = Object.keys(subjectMap).map(k => ({ value: subjectMap[k], name: k }));

        const pieChart = echarts.init(document.getElementById('subjectPieChart'));
        pieChart.setOption({
            color: ['#0d6efd', '#20c997', '#ffc107', '#fd7e14', '#6610f2'],
            tooltip: { trigger: 'item' },
            series: [{
                type: 'pie',
                radius: '70%',
                data: pieData,
                label: { color: '#333' }
            }]
        });

        const typeMap = {};
        tasks.forEach(t => typeMap[t.type] = (typeMap[t.type] || 0) + 1);

        const barChart = echarts.init(document.getElementById('typeBarChart'));
        barChart.setOption({
            tooltip: { trigger: 'axis' },
            grid: { top: 10, bottom: 20, left: 40, right: 10 },
            xAxis: { type: 'category', data: Object.keys(typeMap), axisLabel: { color: '#666' } },
            yAxis: { type: 'value', splitLine: { show: true, lineStyle: { type: 'dashed' } }, axisLabel: { color: '#666' } },
            series: [{
                data: Object.values(typeMap),
                type: 'bar',
                itemStyle: { color: '#0dcaf0', borderRadius: [4, 4, 0, 0] },
                barWidth: '30%'
            }]
        });

        window.onresize = function() {
            pieChart.resize();
            barChart.resize();
        };
    },

    showDetail(text) {
        document.getElementById('modalMethod').innerText = text;
        new bootstrap.Modal(document.getElementById('taskDetailModal')).show();
    },

    loadHistory() {
        const history = localStorage.getItem('choicebot_last_plan');
        if (history) {
            const data = JSON.parse(history);
            document.getElementById('emptyState').classList.add('d-none');
            this.render(data);
        }
    },

    clearData() {
        if(confirm('确定要清空所有计划数据吗？')) {
            localStorage.removeItem('choicebot_last_plan');
            location.reload();
        }
    },

    filterTasks(priority) {
        document.querySelectorAll('.btn-outline-primary').forEach(b => b.classList.remove('active'));
        event.target.classList.add('active');

        const items = document.querySelectorAll('.task-item');
        items.forEach(item => {
            if (priority === 'all' || item.classList.contains(`priority-${priority}`)) {
                item.style.display = 'block';
            } else {
                item.style.display = 'none';
            }
        });
    },

    // === 新增功能：智能诊断 ===
    async autoDiagnose() {
        const input = document.getElementById('weaknessInput');
        const originalPlaceholder = input.placeholder;

        input.placeholder = "正在分析错题本...";
        input.disabled = true;

        try {
            const res = await fetch('/api/study-plan/weakness-analysis');
            const data = await res.json();

            if (data.success) {
                // 打字机效果填入
                this.typeWriter(input, data.weakness);
            } else {
                alert(data.message || "暂无足够错题数据");
                input.placeholder = originalPlaceholder;
            }
        } catch (err) {
            console.error(err);
            input.placeholder = originalPlaceholder;
        } finally {
            input.disabled = false;
        }
    },

    // 辅助：打字机效果
    typeWriter(element, text) {
        element.value = "";
        let i = 0;
        const speed = 30;
        function type() {
            if (i < text.length) {
                element.value += text.charAt(i);
                i++;
                setTimeout(type, speed);
            }
        }
        type();
    },

    // === 新增功能：保存为图片 ===
    saveAsImage() {
        const element = document.getElementById('planCardExport');
        const btn = event.currentTarget;
        const originalText = btn.innerHTML;

        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>生成中...';
        btn.disabled = true;

        const watermark = element.querySelector('.show-on-export');
        if(watermark) watermark.classList.remove('d-none');

        html2canvas(element, {
            scale: 2,
            useCORS: true,
            backgroundColor: "#ffffff"
        }).then(canvas => {
            const link = document.createElement('a');
            link.download = `我的学习计划_${new Date().toLocaleDateString()}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();

            btn.innerHTML = originalText;
            btn.disabled = false;
            if(watermark) watermark.classList.add('d-none');
        }).catch(err => {
            console.error('截图失败:', err);
            btn.innerHTML = '导出失败';
            setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2000);
        });
    }
};

document.addEventListener('DOMContentLoaded', () => Planner.init());