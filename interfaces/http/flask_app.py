import os
import uuid
from typing import Optional

from flask import Flask, jsonify, request
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
    upload_folder = os.path.join(config.data.data_dir, "uploads")
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

    @app.route("/api/ready", methods=["GET"])
    def readiness_check():
        try:
            detail = container.readiness()
            return jsonify({"success": True, "status": "ready", "data": detail})
        except Exception:
            app.logger.exception("Readiness check failed")
            return jsonify({"success": False, "status": "not_ready", "message": "业务服务尚未就绪"}), 503

    @app.before_request
    def check_processing_readiness():
        if request.path in {"/api/upload", "/api/upload_text"}:
            try:
                container.readiness()
            except Exception:
                app.logger.exception("Order processing unavailable")
                return jsonify({"success": False, "message": "业务服务尚未就绪，请稍后重试"}), 503

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
        return jsonify({"success": result.get("success", False), "data": to_jsonable(result)}), status_code

    @app.route("/api/upload_text", methods=["POST"])
    def upload_order_text():
        data = request.get_json(silent=True) or {}

        order_text = data.get("order_text")
        # 类型与空白必须在进入业务链路之前拦下：process_order_from_text 会先落一条
        # 订单再跑流水线，非法输入因此会留下一条注定失败、且界面上无法清理的订单。
        if not isinstance(order_text, str) or not order_text.strip():
            return jsonify(
                {
                    "success": False,
                    "message": "order_text is required and must be a non-empty string",
                }
            ), 400

        result = container.orchestrator.process_order_from_text(order_text)
        status_code = 200 if result.get("success") else 400
        return jsonify({"success": result.get("success", False), "data": to_jsonable(result)}), status_code

    @app.route("/api/orders", methods=["GET"])
    def list_orders():
        return jsonify({"success": True, "data": to_jsonable(container.orchestrator.list_orders())})

    @app.route("/api/orders/<order_id>", methods=["GET"])
    def get_order(order_id: str):
        order = container.orchestrator.get_order_detail(order_id)

        if not order:
            return jsonify({"success": False, "message": "Order not found"}), 404

        return jsonify({"success": True, "data": to_jsonable(order)})

    @app.route("/api/orders/<order_id>/trace", methods=["GET"])
    def get_order_trace(order_id: str):
        """协作轨迹：谁在什么时候对谁说了什么、依据是什么（设计文档 §2.3、§5）。"""
        order = container.orchestrator.get_order_detail(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order not found"}), 404
        return jsonify({"success": True, "data": to_jsonable(container.orchestrator.get_trace(order_id))})

    @app.route("/api/orders/<order_id>/tasks", methods=["GET"])
    def get_order_tasks(order_id: str):
        """任务 DAG 状态：按 item/region 扇出的任务与租约（设计文档 §2.4）。"""
        order = container.orchestrator.get_order_detail(order_id)
        if not order:
            return jsonify({"success": False, "message": "Order not found"}), 404
        return jsonify({"success": True, "data": to_jsonable(container.orchestrator.get_tasks(order_id))})

    @app.route("/api/orders/<order_id>/review-suggestion", methods=["POST"])
    def generate_review_suggestion(order_id: str):
        result = container.orchestrator.generate_review_suggestion(order_id)
        if not result.get("success") and result.get("message") == "订单不存在":
            status_code = 404
        elif not result.get("success"):
            status_code = 409
        else:
            status_code = 200
        return jsonify({"success": result.get("success", False), "data": to_jsonable(result)}), status_code

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

        comment = data.get("comment")
        if comment is not None and not isinstance(comment, str):
            return jsonify({"success": False, "message": "comment must be a string"}), 400
        result = container.orchestrator.confirm_order(order_id, {"action": action, "comment": comment})
        status_code = 200 if result.get("success") else 400
        return jsonify({"success": result.get("success", False), "data": to_jsonable(result)}), status_code

    # 框架级错误同样返回 JSON，避免客户端在 4xx/5xx 上拿到 HTML 而无法统一解析。
    @app.errorhandler(413)
    def request_entity_too_large(_error):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"success": False, "message": f"文件超过 {limit_mb} MB 上限"}), 413

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"success": False, "message": "Method not allowed"}), 405

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
    print(f"Starting server on http://localhost:{runtime_config.server.port}")
    app.run(
        host="0.0.0.0",
        port=runtime_config.server.port,
        debug=runtime_config.server.debug,
        threaded=False,
    )
