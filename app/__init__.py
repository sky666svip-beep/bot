# app/__init__.py
from flask import Flask, render_template
from app.config import Config
from app.extensions import db


def create_app(config_class=Config):
    # 1. 实例化 Flask 应用
    app = Flask(__name__)

    # 2. 加载配置
    app.config.from_object(config_class)
    # 静态资源缓存 1 天（让 Cloudflare CDN 缓存 CSS/JS/图片）
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400

    # 3. 初始化扩展
    db.init_app(app)

    # 4. 注册蓝图
    from app.api.routes import api_bp
    from app.api.routes import main as main_bp  # 假设你在 routes.py 里定义了 main 蓝图

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(main_bp)  # 注册搜索路由

    # 测试路由
    @app.route('/')
    def index():
        return render_template('index.html')

    with app.app_context():
        # A. 数据库表结构初始化
        from app import models
        from app.models import QuestionBank  # 显式导入模型类
        db.create_all()
        print("✅ 数据库连接成功，数据已加载")

        # B. 启动 ML 矩阵索引构建
        # 这里不再只是简单的 encode 预热，而是要构建全量数据的向量矩阵
        try:
            print("⏳ 正在初始化模型与向量索引...")
            from app.services.nlp_service import nlp_engine

            # 1. 模型加载到显存
            # 2. 从数据库读取数据 -> 构建 GPU Tensor 矩阵
            nlp_engine.refresh_index(QuestionBank)

            print("🚀 答题助手已就绪 ")

        except Exception as e:
            print(f"❌ AI 引擎启动异常: {e}")
            print("   (如果是第一次运行，请忽略此错误，先运行 advanced_import.py 导入数据)")

    return app