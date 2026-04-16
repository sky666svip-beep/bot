# serve.py - 生产环境入口（Waitress + 崩溃重启 + 访问日志）
import time
import logging
import os
from logging.handlers import RotatingFileHandler
from waitress import serve
from dotenv import load_dotenv

# 加载 .env 环境变量文件
load_dotenv()

# === 访问日志配置 ===
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 访问日志（按 5MB 轮转，保留 5 个备份）
access_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'access.log'),
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding='utf-8'
)
access_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
))
access_logger = logging.getLogger('waitress')
access_logger.addHandler(access_handler)
access_logger.setLevel(logging.INFO)

# 错误日志
error_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, 'error.log'),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding='utf-8'
)
error_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
))
error_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(error_handler)


def create_server_app():
    """创建并初始化 Flask 应用"""
    from app import create_app, db
    from app.models import QuestionBank
    from app.services.nlp_service import nlp_engine

    app = create_app()

    # 注入访问日志中间件
    @app.after_request
    def log_request(response):
        from flask import request
        # 记录日志
        access_logger.info(
            f'{request.remote_addr} - {request.method} {request.path} - {response.status_code}'
        )
        return response

    return app


class CacheControlMiddleware:
    """WSGI 中间件：强制静态资源缓存"""
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        
        def custom_start_response(status, headers, exc_info=None):
            # 如果是静态资源，强制修改 Cache-Control
            if path.startswith('/static/'):
                # 移除原有的 Cache-Control (如果有)
                headers = [(k, v) for k, v in headers if k.lower() != 'cache-control']
                # 添加新的强缓存
                headers.append(('Cache-Control', 'public, max-age=3600'))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)


if __name__ == '__main__':
    try:
        app = create_server_app()
        # 包装 WSGI 中间件
        app = CacheControlMiddleware(app)
        
        print("🚀 ChoiceBot 服务器启动中 (Waitress, 8线程)...")
        print("📡 地址: http://0.0.0.0:5000")
        print("🌐 外网: https://amxsvip.site")
        print(f"📝 日志: {LOG_DIR}")
        
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except KeyboardInterrupt:
        print("\n⏹️ 服务器已手动停止")
    except Exception as e:
        logging.error(f"❌ 服务器致命崩溃并彻底退出: {e}", exc_info=True)
        print(f"❌ 服务器崩溃。进程已终止。请检查 logs/error.log 或者交由外部服务守护系统重启。")
        exit(1)
