/**
 * App.js：程序主入口，负责初始化和事件绑定
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("🚀 答题助手已就绪");

    // 1. 初始化图表看板
    if (typeof Dashboard !== 'undefined') {
        Dashboard.init();
    }

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