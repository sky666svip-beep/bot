/**
 * Dashboard 模块 - 视觉增强版 (南丁格尔玫瑰图 + GitHub 风格热力图)
 */
const Dashboard = {
    pieChart: null,
    heatChart: null,

    init() {
        const pieDom = document.getElementById('pieChart');
        const heatDom = document.getElementById('heatmapChart');
        if (!pieDom || !heatDom) return;

        this.pieChart = echarts.init(pieDom);
        this.heatChart = echarts.init(heatDom);

        // 初始显示加载动画
        this.pieChart.showLoading();
        this.heatChart.showLoading();

        this.loadData();

        window.addEventListener('resize', () => {
            this.pieChart && this.pieChart.resize();
            this.heatChart && this.heatChart.resize();
        });
    },

    async loadData() {
        try {
            const res = await fetch('/api/dashboard');
            const data = await res.json();

            this.pieChart.hideLoading();
            this.heatChart.hideLoading();

            this.renderPie(data.pie);
            this.renderHeatmap(data.heatmap);
        } catch (e) {
            console.error("图表加载失败:", e);
            this.pieChart.hideLoading();
            this.heatChart.hideLoading();
        }
    },

    renderPie(pieData) {
        this.pieChart.setOption({
            tooltip: { trigger: 'item' },
            legend: { top: 'bottom' },
            series: [{
                name: '题目类型',
                type: 'pie',
                radius: [20, 100],
                center: ['50%', '40%'],
                roseType: 'area', // 玫瑰图模式
                itemStyle: { borderRadius: 7 },
                data: pieData.length ? pieData : [{ name: '暂无数据', value: 0 }]
            }]
        });
    },

    renderHeatmap(heatmapData) {
        const currentYear = new Date().getFullYear();
        this.heatChart.setOption({
            tooltip: {
                formatter: function (p) {
                    return p.value[0] + ' : 刷题 ' + p.value[1] + ' 道';
                }
            },
            visualMap: {
                min: 0,
                max: 10,
                type: 'piecewise',
                orient: 'horizontal',
                left: 'center',
                top: 0,
                textStyle: { color: '#000' },
                inRange: {
                    color: ['#ebedf0', '#9be9a8', '#40c463', '#30a14e', '#216e39']
                },
                calculable: false,
                outOfRange: { color: '#216e39' }
            },
            calendar: {
                top: 50,
                left: 30,
                right: 30,
                cellSize: ['auto', 25], // 这里微调了一下高度，适配卡片
                range: currentYear,
                itemStyle: { borderWidth: 0.5 },
                yearLabel: { show: false }
            },
            series: {
                type: 'heatmap',
                coordinateSystem: 'calendar',
                data: heatmapData
            }
        });
    }
};

/**
 * App.js：程序主入口，负责初始化和事件绑定
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 答题助手已就绪");

    // 1. 初始化图表看板
    Dashboard.init();

    // 2. 全局事件绑定
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', (e) => {
            // 防止冒泡触发祖先的事件
            e.stopPropagation();
            SearchEngine.processAndSolve();
        });
    }

    // 绑定 Enter 键快捷搜索 (Ctrl + Enter)
    const rawTextArea = document.getElementById('rawText');
    if (rawTextArea) {
        rawTextArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) { 
                SearchEngine.processAndSolve();
            }
        });
    }

    // 3. 复制功能逻辑
    window.copyAnswer = function() {
        const ans = document.getElementById('targetAnswer').innerText;
        if (!ans) return;
        navigator.clipboard.writeText(ans).then(() => {
            const tip = document.getElementById('copyTip');
            if(tip){
                tip.innerText = "已复制!";
                setTimeout(() => tip.innerText = "复制", 2000);
            }
        }).catch(err => {
            console.error("复制失败:", err);
            alert("复制失败，请手动选择复制");
        });
    };
});