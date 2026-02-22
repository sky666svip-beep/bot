# app/api/auth.py
import re
import requests
import random
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from app.extensions import db, mail
from app.models import User, VerificationCode

auth_bp = Blueprint('auth', __name__)

# 用户名规则：仅允许中文、英文、数字、下划线，大小写敏感
_USERNAME_RE = re.compile(r'^[\u4e00-\u9fa5a-zA-Z0-9_]+$')
# 邮箱简单规则验证
_EMAIL_RE = re.compile(r'^\S+@\S+\.\S+$')

def verify_turnstile(token):
    """
    通过 Cloudflare 后端接口校验人机验证 Token 的有效性
    """
    # 本地开发环境跳过验证
    if request.remote_addr in ['127.0.0.1', '::1'] or request.host.startswith('localhost'):
        return True

    if not token:
        return False
    
    try:
        from flask import current_app
        secret_key = current_app.config.get('CF_TURNSTILE_SECRET_KEY')
        
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret_key,
                'response': token,
                'remoteip': request.remote_addr
            },
            timeout=5
        )
        result = response.json()
        return result.get('success', False)
    except Exception as e:
        # 如果网络请求失败，为避免阻断用户，通常可根据业务需求选择通过或拦截。
        # 此处选择保守拦截，需记录日志。
        print(f"Turnstile verify error: {e}")
        return False


def _safe_redirect(fallback='index'):
    """防止开放重定向：仅允许站内相对路径"""
    target = request.args.get('next', '')
    if target and target.startswith('/'):
        return redirect(target)
    return redirect(url_for(fallback))


@auth_bp.route('/api/auth/send_code', methods=['POST'])
def send_code():
    """发送邮箱验证码API"""
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    purpose = data.get('purpose', 'verify') # 默认为注册绑定验证
    
    if not _EMAIL_RE.match(email):
        return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400
        
    # 频率限制：检查最近60秒是否发送过
    one_minute_ago = datetime.utcnow() - timedelta(seconds=60)
    recent_code = VerificationCode.query.filter(
        VerificationCode.email == email,
        VerificationCode.created_at >= one_minute_ago
    ).first()
    
    if recent_code:
        return jsonify({'success': False, 'message': '发送频繁，请 60 秒后再试'}), 429
        
    # 生成 6 位纯数字验证码
    code = f"{random.randint(0, 999999):06d}"
    
    # 根据用途定义邮件标题
    subject_map = {
        'verify': '账号注册与绑定验证码',
        'reset_password': '找回与重置密码验证码'
    }
    subject = subject_map.get(purpose, '邮箱验证码')
    
    try:
        msg = Message(subject=f"[{subject}] - 智能答题助手",
                      recipients=[email],
                      body=f"您的验证码是：{code} \n此验证码在 5 分钟内有效。如果这不是您本人的操作，请忽略此邮件。")
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email: {e}")
        return jsonify({'success': False, 'message': '邮件发送失败，请稍后重试'}), 500

    # 清理此邮箱旧的未使用的对应 purpose 的验证码
    VerificationCode.query.filter_by(email=email, purpose=purpose, is_used=False).delete()

    # 记录到数据库
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    new_code = VerificationCode(email=email, code=code, purpose=purpose, expires_at=expires_at)
    db.session.add(new_code)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '验证码已发送，请查收邮箱'})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    from flask import current_app
    site_key = current_app.config.get('CF_TURNSTILE_SITE_KEY')

    if request.method == 'POST':
        from flask import current_app
        site_key = current_app.config.get('CF_TURNSTILE_SITE_KEY')
        
        turnstile_response = request.form.get('cf-turnstile-response')
        if not verify_turnstile(turnstile_response):
            flash('人机验证失败，请重试', 'error')
            return render_template('login.html', turnstile_site_key=site_key)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()
        if not user and _EMAIL_RE.match(username):
            user = User.query.filter_by(email=username).first()
            
        if user and user.check_password(password):
            login_user(user, remember=remember)
            return _safe_redirect()

        flash('用户名或密码错误', 'error')

    return render_template('login.html', turnstile_site_key=site_key)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    from flask import current_app
    site_key = current_app.config.get('CF_TURNSTILE_SITE_KEY')

    if request.method == 'POST':
        from flask import current_app
        site_key = current_app.config.get('CF_TURNSTILE_SITE_KEY')
        
        turnstile_response = request.form.get('cf-turnstile-response')
        if not verify_turnstile(turnstile_response):
            flash('人机验证失败，请重试', 'error')
            return render_template('register.html', turnstile_site_key=site_key)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        email = request.form.get('email', '').strip()
        email_code = request.form.get('email_code', '').strip()

        # 校验链
        if len(username) < 3 or len(username) > 15:
            flash('用户名长度需在 3-15 个字符之间', 'error')
        elif not _USERNAME_RE.match(username):
            flash('用户名仅支持中文、英文、数字和下划线', 'error')
        elif len(password) < 6 or len(password) > 15:
            flash('密码长度需在 6-15 个字符之间', 'error')
        elif password != confirm:
            flash('两次密码输入不一致', 'error')
        elif User.query.filter_by(username=username).first():
            flash('用户名已被注册', 'error')
        else:
            # 邮箱验证逻辑
            if email:
                if not _EMAIL_RE.match(email):
                    flash('邮箱格式不正确', 'error')
                    return render_template('register.html', turnstile_site_key=site_key)
                if User.query.filter_by(email=email).first():
                    flash('该邮箱已被绑定，请更换或直接登录', 'error')
                    return render_template('register.html', turnstile_site_key=site_key)
                
                # 核对验证码
                vc = VerificationCode.query.filter_by(
                    email=email, purpose='verify', code=email_code, is_used=False
                ).first()
                if not vc or vc.expires_at < datetime.utcnow():
                    flash('邮箱验证码错误或已过期', 'error')
                    return render_template('register.html', turnstile_site_key=site_key)
                # 标记使用
                vc.is_used = True

            try:
                user = User(username=username, email=email if email else None)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                login_user(user, remember=True)
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                print(f"Register err: {e}")
                flash('注册失败，请稍后重试', 'error')

    return render_template('register.html', turnstile_site_key=site_key)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        code = request.form.get('email_code', '').strip()
        new_password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not email or not code or not new_password or not confirm:
            flash('请填写完整信息', 'error')
        elif new_password != confirm:
            flash('两次密码不一致', 'error')
        elif len(new_password) < 6 or len(new_password) > 15:
            flash('密码长度需在 6-15 个字符之间', 'error')
        else:
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('该邮箱未绑定任何账号', 'error')
            else:
                vc = VerificationCode.query.filter_by(
                    email=email, purpose='reset_password', code=code, is_used=False
                ).first()
                if not vc or vc.expires_at < datetime.utcnow():
                    flash('验证码错误或已过期', 'error')
                else:
                    # 修改密码
                    user.set_password(new_password)
                    vc.is_used = True
                    db.session.commit()
                    flash('密码重置成功，请使用新密码登录', 'success')
                    return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')
        
        # === 动作：绑定/换绑邮箱 ===
        if action == 'bind_email':
            new_email = request.form.get('email', '').strip()
            code = request.form.get('email_code', '').strip()
            
            if not new_email or not code:
                flash('请提供邮箱及验证码', 'error')
            elif not _EMAIL_RE.match(new_email):
                flash('邮箱格式不正确', 'error')
            elif User.query.filter(User.email == new_email, User.id != current_user.id).first():
                flash('该邮箱已被其他账号绑定', 'error')
            else:
                vc = VerificationCode.query.filter_by(
                    email=new_email, purpose='verify', code=code, is_used=False
                ).first()
                if not vc or vc.expires_at < datetime.utcnow():
                    flash('验证码错误或已过期', 'error')
                else:
                    current_user.email = new_email
                    vc.is_used = True
                    db.session.commit()
                    flash('邮箱绑定成功！', 'success')

        # === 动作：修改密码 ===
        elif action == 'change_password':
            old_password = request.form.get('old_password', '')
            new_password = request.form.get('new_password', '')
            confirm = request.form.get('confirm', '')
            code = request.form.get('email_code', '').strip() # 必须先通过邮箱验证
            
            if not current_user.email:
                flash('请先绑定邮箱再修改密码', 'error')
            elif not old_password or not new_password or not confirm or not code:
                flash('请填写完整信息', 'error')
            elif not current_user.check_password(old_password):
                flash('原密码不正确', 'error')
            elif new_password == old_password:
                flash('新密码不能与原密码相同', 'error')
            elif new_password != confirm:
                flash('两次输入的新密码不一致', 'error')
            elif len(new_password) < 6 or len(new_password) > 15:
                flash('新密码长度需在 6-15 个字符之间', 'error')
            else:
                vc = VerificationCode.query.filter_by(
                    email=current_user.email, purpose='reset_password', code=code, is_used=False
                ).first()
                if not vc or vc.expires_at < datetime.utcnow():
                    flash('安全验证码错误或已过期', 'error')
                else:
                    current_user.set_password(new_password)
                    vc.is_used = True
                    db.session.commit()
                    flash('密码重置成功，下次请使用新密码登录。', 'success')
                    
        return redirect(url_for('auth.profile'))
        
    return render_template('profile.html', user=current_user)
