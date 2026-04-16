# app/__init__.py
from flask import Flask, render_template, jsonify, request, redirect, url_for
from app.config import Config
from app.extensions import db, login_manager, mail


def create_app(config_class=Config):
    # 1. 实例化 Flask 应用
    app = Flask(__name__)

    # 2. 加载配置
    app.config.from_object(config_class)
    # 静态资源缓存 1 天（让 Cloudflare CDN 缓存 CSS/JS/图片）
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600

    # 3. 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    mail.init_app(app)

    # user_loader 回调
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # AJAX 请求未登录时返回 401 JSON（而非重定向到登录页）
    @login_manager.unauthorized_handler
    def unauthorized():
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': '请先登录', 'redirect': '/login'}), 401
        return redirect(url_for('auth.login'))

    # 4. 注册蓝图
    from app.api.routes import api_bp
    from app.api.views import page_bp
    from app.api.api_search import search_bp
    from app.api.auth import auth_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(search_bp, url_prefix='/api')
    app.register_blueprint(page_bp)
    app.register_blueprint(auth_bp)

    # 首页路由
    @app.route('/')
    def index():
        return render_template('index.html')

    # 全局健康检查入口
    @app.route('/health')
    def health_check():
        try:
            from app.services.nlp_service import nlp_engine
            health_data = nlp_engine.get_health_status()
            return jsonify({
                "status": "ok" if health_data["is_ready"] else "loading",
                "message": "全局服务与引擎就绪" if health_data["is_ready"] else "各子系统正在预热分配资源，请耐心等待...",
                "metrics": health_data
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": f"健康探测失败: {str(e)}"}), 500

    with app.app_context():
        # A. 数据库表结构初始化
        from app import models
        from app.models import QuestionBank, Formula  # 显式导入模型类
        db.create_all()
        print("数据库连接成功，数据已加载")

        # B. 启动 ML 矩阵异步初始化 (后台加载)
        try:
            from app.services.nlp_service import nlp_engine
            import threading
            
            def init_ai():
                with app.app_context():
                    print(" [后台线程] 引擎启动中...加载模型大矩阵可能会花费数秒。")
                    nlp_engine.background_initialize(QuestionBank, Formula)

            thread = threading.Thread(target=init_ai, daemon=True, name="ML_Init_Thread")
            thread.start()
        except Exception as e:
            print(f"AI 引擎调度异常: {e}")

    return app
