from flask import Flask
from .extensions import db, login_manager, csrf, limiter, migrate, oauth
from .filters import register_filters


def create_app(config_name=None):
    app = Flask(__name__)

    if config_name == 'testing':
        app.config.from_object('app.config.TestConfig')
    elif config_name == 'production':
        app.config.from_object('app.config.ProdConfig')
    else:
        app.config.from_object('app.config.DevConfig')

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)

    register_filters(app)

    from .auth import auth_bp
    from .public import public_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    return app
