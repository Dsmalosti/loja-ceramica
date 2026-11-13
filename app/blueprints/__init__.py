def register_blueprints(app):
    from .account import bp as account_bp
    from .admin import bp as admin_bp
    from .cart import bp as cart_bp
    from .payments import bp as payments_bp
    from .public import bp as public_bp
    from .shop import bp as shop_bp

    # Estes módulos só acrescentam rotas ao blueprint "admin"; precisam ser
    # importados ANTES de registrar o blueprint.
    from . import admin_categorias, admin_cursos, admin_produtos, admin_servicos  # noqa: F401

    app.register_blueprint(public_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
