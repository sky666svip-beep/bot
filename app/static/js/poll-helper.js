/**
 * poll-helper.js — 通用异步任务轮询辅助模块
 * 使用指数退避策略：初始 800ms，每次翻倍，最大间隔不超过 6s
 */
const TaskPoller = {
    /**
     * 轮询任务直到完成或超时（指数退避）
     * @param {string} taskId  - 后端返回的任务 ID
     * @param {object} opts    - 可选配置
     * @param {number} opts.initInterval - 首次轮询间隔，默认 800ms
     * @param {number} opts.maxInterval  - 最大轮询间隔，默认 6000ms
     * @param {number} opts.timeout      - 超时时间，默认 80s
     * @returns {Promise<any>} 任务结果
     */
    async poll(taskId, opts = {}) {
        const initInterval = opts.initInterval || 800;
        const maxInterval = opts.maxInterval || 6000;
        const timeout = opts.timeout || 80000;
        const start = Date.now();
        let interval = initInterval;

        while (Date.now() - start < timeout) {
            const res = await fetch(`/api/task/${taskId}/status`);
            if (!res.ok) throw new Error(`轮询失败: HTTP ${res.status}`);
            const data = await res.json();

            if (data.status === 'done') return data.result;
            if (data.status === 'error') throw new Error(data.error || '任务执行失败');
            if (data.status === 'not_found') throw new Error('任务不存在');

            // pending / running → 指数退避等待
            await new Promise(r => setTimeout(r, interval));
            interval = Math.min(interval * 1.5, maxInterval);
        }
        throw new Error('任务超时，请稍后重试');
    },

    /**
     * 提交 + 轮询的一体化封装
     * 发起请求 → 拿到 task_id → 指数退避轮询至完成
     * @param {string} url      - 接口地址
     * @param {object} fetchOpts - fetch 参数
     * @param {object} pollOpts  - 轮询配置
     * @returns {Promise<any>} 任务结果
     */
    async submitAndPoll(url, fetchOpts = {}, pollOpts = {}) {
        const res = await fetch(url, fetchOpts);
        const json = await res.json();

        // 后端返回 202 + task_id → 走轮询
        if (json.task_id) {
            return this.poll(json.task_id, pollOpts);
        }
        // 同步返回（快速接口不需要异步化）
        return json;
    }
};
