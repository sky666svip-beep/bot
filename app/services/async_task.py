# app/services/async_task.py — 进程内异步任务引擎
# 基于 ThreadPoolExecutor，将 LLM/PDF 等重 I/O 操作卸载到后台线程
# WSGI 线程仅负责提交任务和查询结果（毫秒级操作）

import secrets
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor

# 任务结果 TTL（秒），过期自动清理防止内存泄漏
_RESULT_TTL = 300  # 5 分钟

# 任务队列最大积压量，超过此值拒绝新任务
_MAX_PENDING = 64

class TaskManager:
    """进程内异步任务管理器（单例）"""

    def __init__(self, max_workers=16):
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="async_task")
        self._tasks = {}       # task_id -> { status, result, error, owner, created_at, finished_at }
        self._lock = threading.Lock()
        self._semaphore = threading.Semaphore(_MAX_PENDING)
        # 启动过期清理守护线程
        self._cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner.start()

    # ─── 公开 API ────────────────────────────────────────────

    def submit(self, fn, *args, app=None, owner=None, **kwargs):
        """
        提交任务到后台线程池，返回 task_id。
        owner: 任务归属标识（如用户 ID），用于轮询时做权限校验。
        """
        # 队列背压保护：超过上限直接拒绝
        if not self._semaphore.acquire(blocking=False):
            raise RuntimeError("服务繁忙，请稍后再试")

        # 加密级随机 task_id（32 字节 hex = 64 字符），防止遍历猜测
        task_id = secrets.token_hex(16)
        with self._lock:
            self._tasks[task_id] = {
                "status": "pending",
                "result": None,
                "error": None,
                "owner": owner,
                "created_at": time.time(),
                "finished_at": None,
            }

        def _worker():
            with self._lock:
                self._tasks[task_id]["status"] = "running"
            try:
                if app is not None:
                    with app.app_context():
                        try:
                            result = fn(*args, **kwargs)
                        finally:
                            # 清理线程级 db.session，防止连接泄漏
                            try:
                                from app.extensions import db
                                db.session.remove()
                            except Exception:
                                pass
                else:
                    result = fn(*args, **kwargs)
                with self._lock:
                    self._tasks[task_id]["status"] = "done"
                    self._tasks[task_id]["result"] = result
                    self._tasks[task_id]["finished_at"] = time.time()
            except Exception as e:
                logging.error(f"异步任务 {task_id[:8]}... 执行失败: {e}", exc_info=True)
                with self._lock:
                    self._tasks[task_id]["status"] = "error"
                    self._tasks[task_id]["error"] = str(e)
                    self._tasks[task_id]["finished_at"] = time.time()
            finally:
                self._semaphore.release()

        self._pool.submit(_worker)
        return task_id

    def get_status(self, task_id, owner=None):
        """
        查询任务状态。
        owner: 调用者身份，非空时与任务归属比对，不匹配则返回 not_found。
        """
        with self._lock:
            info = self._tasks.get(task_id)
        if info is None:
            return {"status": "not_found"}
        # 权限校验：任务有 owner 且与请求者不匹配 → 当作不存在
        if info["owner"] is not None and owner is not None and info["owner"] != owner:
            return {"status": "not_found"}
        resp = {"status": info["status"]}
        if info["status"] == "done":
            resp["result"] = info["result"]
        elif info["status"] == "error":
            resp["error"] = info["error"]
        return resp

    # ─── 内部方法 ────────────────────────────────────────────

    def _cleanup_loop(self):
        """定时清理已完成或失败的过期任务"""
        while True:
            time.sleep(60)
            now = time.time()
            expired = []
            with self._lock:
                for tid, info in self._tasks.items():
                    if info["finished_at"] and (now - info["finished_at"]) > _RESULT_TTL:
                        expired.append(tid)
                for tid in expired:
                    del self._tasks[tid]
            if expired:
                logging.debug(f"已清理 {len(expired)} 个过期任务")


# 全局单例
task_mgr = TaskManager(max_workers=16)
