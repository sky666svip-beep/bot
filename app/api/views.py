from flask import Blueprint, render_template

# 独立出负责页面渲染的 Blueprint
page_bp = Blueprint('page', __name__)

# === 页面渲染路由 ===
@page_bp.route('/view-history')
def view_history(): return render_template('history.html')

@page_bp.route('/formulas')
def formulas(): return render_template('formulas.html')

@page_bp.route('/calculator')
def calculator(): return render_template('calculator.html')

@page_bp.route('/essay-correction')
def essay_correction(): return render_template('essay.html')

@page_bp.route('/study_plan')
def study_plan(): return render_template('study_plan.html')

@page_bp.route('/simulation-exam')
def simulation_exam(): return render_template('simulation_exam.html')

@page_bp.route('/poetry')
def poetry(): return render_template('poetry.html')

@page_bp.route('/word_match')
def word_match(): return render_template('word_match.html')

@page_bp.route('/redesign')
def redesign_preview(): return render_template('index_redesign.html')

@page_bp.route('/idiom_pk')
def idiom_pk_page(): return render_template('idiom_pk.html')

@page_bp.route('/idioms_all')
def idioms_all_page(): return render_template('idioms_all.html')

@page_bp.route('/idiom/<int:id>')
def idiom_detail_page(id): 
    return render_template('idiom_detail.html', idiom_id=id)

@page_bp.route('/Major_historical_events')
def Major_historical_events_page(): return render_template('Major_historical_events.html')

@page_bp.route('/Biology')
def Biology_page(): return render_template('Biology.html')

@page_bp.route('/Chemistry')
def Chemistry_page(): return render_template('Chemistry.html')

@page_bp.route('/Geography')
def Geography_page(): return render_template('Geography.html')
@page_bp.route('/function')
def function_page(): return render_template('function.html')
