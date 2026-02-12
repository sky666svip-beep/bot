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