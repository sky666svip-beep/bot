/**
 * App.js：程序主入口，负责初始化和事件绑定
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 AI 答题助手已就绪");

    // 1. 初始化 UI 特效 (樱花与时钟)
    if (typeof UIEffects !== 'undefined') {
        // 如果 initEffects 在脚本里叫 initEffects 而不是 initSakura，请对应修改
        if (UIEffects.initClock) UIEffects.initClock();
        if (UIEffects.initSakura) UIEffects.initSakura();
        else if (typeof initEffects === 'function') initEffects();
    }

    // 2. 初始化图表看板
    if (typeof Dashboard !== 'undefined') {
        Dashboard.init();
    }

    // 3. 初始化错题本 (如果已编写 notebook.js)
    if (typeof Notebook !== 'undefined' && Notebook.refreshFavorites) {
        Notebook.refreshFavorites();
    }

    // 4. 全局事件绑定
    const submitBtn = document.getElementById('submitBtn');
    if (submitBtn) {
        submitBtn.addEventListener('click', () => SearchEngine.processAndSolve());
    }

    // 绑定 Enter 键快捷搜索
    const rawTextArea = document.getElementById('rawText');
    if (rawTextArea) {
        rawTextArea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.ctrlKey) { // Ctrl + Enter 触发
                SearchEngine.processAndSolve();
            }
        });
    }

    // 5. 复制功能逻辑
    window.copyAnswer = function() {
        const ans = document.getElementById('targetAnswer').innerText;
        navigator.clipboard.writeText(ans).then(() => {
            const tip = document.getElementById('copyTip');
            tip.innerText = "已复制!";
            setTimeout(() => tip.innerText = "复制", 2000);
        });
    };
});