"""routes/__init__.py — 註冊所有 Flask Blueprints。"""

from flask import Flask

from routes.upload import bp as upload_bp
from routes.analysis import bp as analysis_bp
from routes.history import bp as history_bp
from routes.compare import bp as compare_bp
from routes.ai import bp as ai_bp


def register_blueprints(app: Flask) -> None:
    """將所有路由 blueprint 掛載到 Flask app。"""
    app.register_blueprint(upload_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(compare_bp)
    app.register_blueprint(ai_bp)
