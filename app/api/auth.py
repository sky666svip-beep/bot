# app/api/auth.py
import re
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

# 用户名规则：仅允许中文、英文、数字、下划线，大小写敏感
_USERNAME_RE = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$')


def _safe_redirect(fallback='index'):
    """防止开放重定向：仅允许站内相对路径"""
    target = request.args.get('next', '')
    if target and target.startswith('/'):
        return redirect(target)
    return redirect(url_for(fallback))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            return _safe_redirect()

        flash('用户名或密码错误', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        # 校验链
        if len(username) < 2 or len(username) > 15:
            flash('用户名长度需在 2-15 个字符之间', 'error')
        elif not _USERNAME_RE.match(username):
            flash('用户名仅支持中文、英文、数字和下划线', 'error')
        elif len(password) < 6 or len(password) > 15:
            flash('密码长度需在 6-15 个字符之间', 'error')
        elif password != confirm:
            flash('两次密码输入不一致', 'error')
        elif User.query.filter_by(username=username).first():
            flash('用户名已被注册', 'error')
        else:
            try:
                user = User(username=username)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                return redirect(url_for('index'))
            except Exception:
                db.session.rollback()
                flash('注册失败，请稍后重试', 'error')

    return render_template('register.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
