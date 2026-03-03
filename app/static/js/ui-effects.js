/**
 * UI 增强模块：樱花 + 果冻时钟
 */
const UIEffects = {
    // --- 1. 果冻时钟逻辑 ---
    initClock() {
        const hourEl = document.getElementById('hour');
        const minEl = document.getElementById('minute');
        const secEl = document.getElementById('second');

        if (!hourEl) return;

        let lastH = '', lastM = '', lastS = '';

        const updateTime = () => {
            const now = new Date();
            const h = String(now.getHours()).padStart(2, '0');
            const m = String(now.getMinutes()).padStart(2, '0');
            const s = String(now.getSeconds()).padStart(2, '0');

            const updateUnit = (el, newVal, oldVal) => {
                if (newVal !== oldVal) {
                    el.innerText = newVal;
                    el.classList.remove('jelly-animate');
                    void el.offsetWidth;
                    el.classList.add('jelly-animate');
                }
            };

            updateUnit(hourEl, h, lastH);
            updateUnit(minEl, m, lastM);
            updateUnit(secEl, s, lastS);

            lastH = h; lastM = m; lastS = s;
        };

        updateTime();
        setInterval(updateTime, 1000);
    },

    // --- 2. 樱花特效逻辑  ---
    initSakura() {
        const container = document.getElementById('sakura-container');
        if (!container) return;

        const createSakura = (isInitial = false, parent = container) => {
            const sakura = document.createElement('div');
            sakura.classList.add('sakura');
            const size = Math.random() * 10 + 15;
            sakura.style.width = `${size}px`;
            sakura.style.height = `${size}px`;
            sakura.style.left = `${Math.random() * 100}%`;
            sakura.style.top = isInitial ? `${Math.random() * 100}%` : `-10%`;
            const duration = Math.random() * 5 + 6;
            sakura.style.animationDuration = `${duration}s`;
            sakura.style.opacity = Math.random() * 0.5 + 0.3;
            
            parent.appendChild(sakura);
            
            // 确保元素自动销毁
            setTimeout(() => {
                if (sakura && sakura.parentNode) sakura.remove();
            }, duration * 1000);
        };

        // 使用 DocumentFragment 批量创建初始花瓣，减少重绘
        const fragment = document.createDocumentFragment();
        for (let i = 0; i < 10; i++) { // 初始数量
            createSakura(true, fragment);
        }
        container.appendChild(fragment);

        setInterval(() => createSakura(false), 3000); // 频率降低
    }
};

// --- 初始化入口 ---
document.addEventListener('DOMContentLoaded', () => {
    UIEffects.initClock();
    UIEffects.initSakura();
    console.log("UI Effects 模块已启动 (原版果冻时钟 + 樱花)");
});