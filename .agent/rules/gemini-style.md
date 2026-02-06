---
trigger: manual
---

# Gemini 彩虹流光风格组件使用指南

## 组件位置
- **CSS**: `app/static/css/gemini-search.css`
- **HTML模板**: `app/templates/components/gemini_search.html`
- **JS**: `app/static/js/gemini-search.js`

## 快速复用方法

### 1. 搜索框组件 (完整版)
在页面中直接 include：
```html
<!-- head 中 -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/gemini-search.css') }}">

<!-- body 中 -->
{% set search_placeholder = "自定义占位符..." %}
{% set search_input_id = "mySearchInput" %}
{% set show_ai_button = true %}
{% set show_doc_button = false %}
{% set show_img_button = false %}
{% set ai_button_text = "NLP 语义搜索" %}
{% include 'components/gemini_search.html' %}

<!-- 底部 -->
<script src="{{ url_for('static', filename='js/gemini-search.js') }}"></script>
```

### 2. 彩虹流光按钮 (独立使用)
HTML 结构：
```html
<div class="rainbow-btn-wrapper">
    <div class="rainbow-blur-layer"><div class="rainbow-gradient"></div></div>
    <div class="rainbow-sharp-layer"><div class="rainbow-gradient"></div></div>
    <button class="btn rainbow-btn-inner">按钮文字</button>
</div>
```
需要引入 `style.css` 中的 `.rainbow-*` 系列样式。

### 3. 彩虹流光边框 (任意容器)
核心 CSS 结构：
```css
.my-container {
    position: relative;
    padding: 2px; /* 边框宽度 */
    border-radius: 12px; /* 圆角 */
}
/* 添加两个光效层 */
.blur-layer, .sharp-layer {
    position: absolute; inset: 0; border-radius: inherit; overflow: hidden;
    pointer-events: none; z-index: 0;
}
.blur-layer { filter: blur(4px); }
/* 光锥动画 */
.gradient {
    background: conic-gradient(
        #3186ff00 0deg, #34a853 36deg, #ffd314 60deg, #ff4641 84deg,
        #3186ff 108deg, #5f63db 132deg, #9b72cb 156deg, #3186ff 180deg,
        #3186ff00 324deg
    );
    height: 200%; top: -50%; position: absolute; scale: 3 1;
    animation: rainbow-rotate 5s linear infinite;
}
@keyframes rainbow-rotate { to { transform: rotate(360deg); } }
/* 内容层 */
.inner {
    position: relative; background: #fff; border-radius: 10px; z-index: 1;
}
```

## AI 提示词模板
当您想让 AI 应用此风格时，可以这样说：
只需在对话中这样说：
“"请参考 @gemini-style.md，为 [XX元素] 添加彩虹流光边框"”
或者更简洁：
“"用 Gemini 彩虹风格给这个按钮加边框动画"
> 请参考 `gemini-search.css` 的彩虹流光风格，为 [目标元素] 添加相同的边框动画效果。
> - 需要/不需要 悬停变化
> - 圆角大小：[Xpx]
> - 动画速度：[Xs]
