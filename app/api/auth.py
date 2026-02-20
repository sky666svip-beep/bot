# app/api/auth.py
from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 已登录用户直接跳转首页
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            # 处理 next 参数，登录后跳转到之前想访问的页面
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))

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

        # 校验
        if len(username) < 2 or len(username) > 20:
            flash('用户名长度需在 2-20 个字符之间', 'error')
        elif len(password) < 6 or len(password) > 15:
            flash('密码长度需在 6-15 个字符之间', 'error')
        elif password != confirm:
            flash('两次密码输入不一致', 'error')
        elif User.query.filter_by(username=username).first():
            flash('用户名已被注册', 'error')
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for('index'))

    return render_template('register.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
