def register_blueprints(app):
    from .account import bp as account_bp
    from .admin import bp as admin_bp
    from .payments import bp as payments_bp
    from .public import bp as public_bp
    from .shop import bp as shop_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(payments_bp)
