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

    with app.app_context():
        # A. 数据库表结构初始化
        from app import models
        from app.models import QuestionBank, Formula  # 显式导入模型类
        db.create_all()
        print("数据库连接成功，数据已加载")

        # B. 启动 ML 矩阵索引构建
        try:
            print("正在初始化模型与向量索引...")
            from app.services.nlp_service import nlp_engine
            nlp_engine.refresh_index(QuestionBank)
            nlp_engine.refresh_formula_index(Formula)
            print("答题助手已就绪 ")
        except Exception as e:
            print(f"AI 引擎启动异常: {e}")
            print("   (如果是第一次运行，请忽略此错误，先运行 advanced_import.py 导入数据)")

    return app
