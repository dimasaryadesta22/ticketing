from flask import jsonify


class ApiError(Exception):
    """Error yang dikirim ke klien sebagai JSON: {"error": {"code", "message"}}."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ValidationError(ApiError):
    def __init__(self, message: str):
        super().__init__(422, "VALIDATION_ERROR", message)


class NotFound(ApiError):
    def __init__(self, message: str = "Data tidak ditemukan"):
        super().__init__(404, "NOT_FOUND", message)


class BusinessRuleError(ApiError):
    """Pelanggaran aturan bisnis (kuota habis, batas 4 tiket, lewat H-1, ...)."""

    def __init__(self, code: str, message: str):
        super().__init__(409, code, message)


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err: ApiError):
        return jsonify(error={"code": err.code, "message": err.message}), err.status

    @app.errorhandler(404)
    def _not_found(_err):
        return jsonify(error={"code": "NOT_FOUND", "message": "Endpoint tidak ditemukan"}), 404

    @app.errorhandler(405)
    def _method(_err):
        return jsonify(error={"code": "METHOD_NOT_ALLOWED", "message": "Method tidak diizinkan"}), 405

    @app.errorhandler(500)
    def _server(_err):
        return jsonify(error={"code": "SERVER_ERROR", "message": "Terjadi kesalahan di server"}), 500
