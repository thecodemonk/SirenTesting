import os
import re

from flask import Flask, send_from_directory, abort, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from .extensions import db, login_manager, csrf, limiter, migrate, oauth
from .filters import register_filters


def create_app(config_name=None):
    app = Flask(__name__)
    # Trust proxy headers (ngrok, nginx) so url_for generates correct https URLs
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

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
    from .members import members_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(members_bp)

    os.makedirs(app.config['MEDIA_FOLDER'], exist_ok=True)

    @app.route('/media/photos/<filename>')
    def media_photo(filename):
        if not re.match(r'^test_\d+(_thumb)?\.jpg$', filename):
            abort(404)
        return send_from_directory(app.config['MEDIA_FOLDER'], filename)

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        # Roll back any in-progress DB transaction so the next request gets a
        # clean session — without this, a 500 mid-transaction can leave the
        # session in a broken state for subsequent requests on the same worker.
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    return app
