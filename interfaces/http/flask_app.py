import os
import uuid
from typing import Optional

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

from application.container import ApplicationContainer
from config import Config
from domain.constants import SUPPORTED_DOCUMENT_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS
from interfaces.http.serializers import to_jsonable


SUPPORTED_UPLOAD_EXTENSIONS = {
    extension.lstrip(".")
    for extension in (SUPPORTED_DOCUMENT_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS)
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in SUPPORTED_UPLOAD_EXTENSIONS


def create_app(
    config: Optional[Config] = None,
    container: Optional[ApplicationContainer] = None,
) -> Flask:
    config = config or Config()
    container = container or ApplicationContainer(config=config)

    app = Flask(__name__)
    CORS(app)

    upload_folder = config.SAMPLE_ORDERS_PATH
    os.makedirs(upload_folder, exist_ok=True)

    app.config["UPLOAD_FOLDER"] = upload_folder
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.extensions["container"] = container

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify(
            {
                "success": True,
                "message": "Service is running",
                "status": "healthy",
            }
        )

    @app.route("/api/upload", methods=["POST"])
    def upload_order():
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file part in the request"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "message": "No file selected for uploading"}), 400

        if not allowed_file(file.filename):
            return jsonify({"success": False, "message": "File type not allowed"}), 400

        sanitized_name = secure_filename(file.filename)
        filename = f"{uuid.uuid4()}_{sanitized_name}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        result = container.orchestrator.process_order_from_document(filepath)
        status_code = 200 if result.get("success") else 400
        return jsonify(to_jsonable(result)), status_code

    @app.route("/api/upload_text", methods=["POST"])
    def upload_order_text():
        data = request.get_json(silent=True) or {}

        order_text = data.get("order_text")
        if not order_text:
            return jsonify({"success": False, "message": "order_text is required"}), 400

        result = container.orchestrator.process_order_from_text(order_text)
        status_code = 200 if result.get("success") else 400
        return jsonify(to_jsonable(result)), status_code

    @app.route("/api/query_status/<order_id>", methods=["GET"])
    def query_status(order_id: str):
        status = container.orchestrator.get_order_status(order_id)

        if not status:
            return jsonify({"success": False, "message": "Order not found"}), 404

        return jsonify({"success": True, "data": to_jsonable(status)})

    @app.route("/api/confirm/<order_id>", methods=["POST"])
    def confirm_order(order_id: str):
        data = request.get_json(silent=True) or {}
        action = data.get("action")

        if action not in {"confirm", "reject"}:
            return jsonify(
                {
                    "success": False,
                    "message": "action is required and must be either confirm or reject",
                }
            ), 400

        result = container.orchestrator.confirm_order(order_id, {"action": action})
        status_code = 200 if result.get("success") else 400
        return jsonify(to_jsonable(result)), status_code

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"success": False, "message": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.exception("Unhandled application error: %s", error)
        return jsonify({"success": False, "message": "Internal server error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    runtime_config = Config()
    print(f"Starting server on http://localhost:{runtime_config.FLASK_PORT}")
    app.run(
        host="0.0.0.0",
        port=runtime_config.FLASK_PORT,
        debug=runtime_config.FLASK_DEBUG,
    )
