from flask import Blueprint, abort, current_app, render_template
from flask_login import current_user

from ..models import Course, Product, Service

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
def exigir_admin():
    """Vale para TODAS as rotas deste blueprint, inclusive as futuras."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if not current_user.is_admin:
        abort(403)


@bp.route("/")
def dashboard():
    return render_template(
        "admin/dashboard.html",
        total_produtos=Product.query.count(),
        produtos_sem_estoque=Product.query.filter_by(ativo=True, estoque=0).count(),
        total_cursos=Course.query.count(),
        total_servicos=Service.query.count(),
    )
