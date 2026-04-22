from pathlib import Path

from flask import Flask, send_from_directory

from ..db import init_db


def create_app(db_path: Path | None = None) -> Flask:
    dist_dir = Path(__file__).parent / "static" / "dist"
    app = Flask(__name__, static_folder=str(dist_dir / "assets"), static_url_path="/assets")

    if db_path is None:
        from ..config import DB_PATH
        db_path = DB_PATH

    app.config["DB_PATH"] = db_path

    db = init_db(db_path)
    db.close()

    from .routes import bp
    app.register_blueprint(bp)

    @app.route("/")
    def index():
        return send_from_directory(str(dist_dir), "index.html")

    return app
