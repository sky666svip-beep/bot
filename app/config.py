# 配置文件 (开发/生产环境配置)
# app/config.py
import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'

    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, '../data/app.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cloudflare Turnstile 配置
    CF_TURNSTILE_SITE_KEY = os.environ.get('CF_TURNSTILE_SITE_KEY', 'YOUR_CLOUDFLARE_TURNSTILE_SITE_KEY')
    CF_TURNSTILE_SECRET_KEY = os.environ.get('CF_TURNSTILE_SECRET_KEY', 'YOUR_CLOUDFLARE_TURNSTILE_SECRET_KEY')

    # QQ 邮箱 SMTP 配置
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.qq.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'true').lower() in ['true', '1', 'yes']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'your_qq_email@qq.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your_qq_auth_code')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)