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

    async submitAndPoll(url, fetchOpts = {}, pollOpts = {}) {
        let res, json;
        const maxRetries = pollOpts.submitMaxRetries || 7;
        let retryInterval = 2000; // 初始退避 2 秒

        for (let i = 0; i < maxRetries; i++) {
            res = await fetch(url, fetchOpts);
            
            try {
                json = await res.json();
            } catch (e) {
                if (res.status === 503) json = { message: "后端引擎预热中..." };
                else throw new Error(`[HTTP ${res.status}] 数据解析失败`);
            }

            if (res.status === 503) {
                console.warn(`[HTTP 503] 模型未就绪，${retryInterval}ms 后进行第 ${i + 1} 次重发...`, json.message);
                
                // 抛出加载中事件，供外层 UI 显示倒计时或重试提示
                window.dispatchEvent(new CustomEvent('engine-loading', { 
                    detail: { attempt: i + 1, message: json.message }
                }));

                await new Promise(r => setTimeout(r, retryInterval));
                retryInterval = Math.min(retryInterval * 1.5, 10000); // 最大不跨越 10s
                continue;
            }
            
            // 请求不再呈现 503，发射就绪事件复位 UI
            if (i > 0) window.dispatchEvent(new CustomEvent('engine-ready'));
            break;
        }

        if (res?.status === 503) {
            throw new Error(`引擎装载极度缓慢或服务过载，请稍后刷新重试`);
        }

        // 后端返回 202 + task_id → 走轮询
        if (json && json.task_id) {
            return this.poll(json.task_id, pollOpts);
        }
        // 同步返回（快速接口不需要异步化）
        return json;
    }
};
