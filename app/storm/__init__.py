from flask import Blueprint

storm_bp = Blueprint('storm', __name__, url_prefix='/storm')

from . import routes  # noqa: E402, F401
