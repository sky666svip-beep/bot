# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

# 初始化扩展，但暂时不绑定 app
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()