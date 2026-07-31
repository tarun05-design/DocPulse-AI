import logging

from flask import Flask, jsonify

from .config import Config
from .extensions import db, jwt, cors

logger = logging.getLogger(__name__)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    from .auth.routes import auth_bp
    from .documents.routes import documents_bp
    from .chat.routes import chat_bp
    from .dashboard.routes import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "DocPulse AI backend"})

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify({"error": "File too large. Max upload size is 25MB."}), 413

    @app.errorhandler(500)
    def internal_error(_e):
        logger.exception("Internal server error")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500

    with app.app_context():
        db.create_all()

    def _prewarm(app_obj):
        with app_obj.app_context():
            try:
                from .services import embeddings
                embeddings._get_model()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Model pre-warming background task: %s", exc)

    import threading
    threading.Thread(target=_prewarm, args=(app,), daemon=True).start()

    logger.info("DocPulse AI backend started")
    return app
