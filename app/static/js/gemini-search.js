/**
 * Gemini 风格搜索框组件 - 交互逻辑
 * 
 * 使用方法:
 * 1. 引入此 JS 文件
 * 2. 在页面中初始化: GeminiSearch.init({ inputId: 'yourInputId', onSearch: (query, isAI) => {} })
 */

const GeminiSearch = {
    config: {
        inputId: 'geminiSearchInput',
        aiToggleId: 'geminiAiToggle',
        onSearch: null,        // 搜索回调: (query, isAIMode) => {}
        onDocUpload: null,     // 文档上传回调: (file) => {}
        onImgUpload: null      // 图片上传回调: (file) => {}
    },
    
    isAIMode: false,
    
    /**
     * 初始化搜索框
     * @param {Object} options - 配置项
     */
    init(options = {}) {
        Object.assign(this.config, options);
        
        const input = document.getElementById(this.config.inputId);
        const aiBtn = document.getElementById(this.config.aiToggleId);
        
        // 回车搜索
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.doSearch();
                }
            });
        }
        
        // AI 模式切换
        if (aiBtn) {
            aiBtn.addEventListener('click', () => this.toggleAI());
        }
    },
    
    /**
     * 执行搜索
     */
    doSearch() {
        const input = document.getElementById(this.config.inputId);
        const query = input ? input.value.trim() : '';
        
        if (query && typeof this.config.onSearch === 'function') {
            this.config.onSearch(query, this.isAIMode);
        }
    },
    
    /**
     * 切换 AI 模式
     */
    toggleAI() {
        this.isAIMode = !this.isAIMode;
        const btn = document.getElementById(this.config.aiToggleId);
        if (btn) {
            btn.classList.toggle('active', this.isAIMode);
        }
        return this.isAIMode;
    },
    
    /**
     * 触发文档上传
     */
    triggerDocUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx,.txt';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file && typeof this.config.onDocUpload === 'function') {
                this.config.onDocUpload(file);
            }
        };
        input.click();
    },
    
    /**
     * 触发图片上传
     */
    triggerImgUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file && typeof this.config.onImgUpload === 'function') {
                this.config.onImgUpload(file);
            }
        };
        input.click();
    },
    
    /**
     * 设置输入框的值
     */
    setValue(value) {
        const input = document.getElementById(this.config.inputId);
        if (input) input.value = value;
    },
    
    /**
     * 获取输入框的值
     */
    getValue() {
        const input = document.getElementById(this.config.inputId);
        return input ? input.value.trim() : '';
    }
};
