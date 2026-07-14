class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, resource: str):
        super().__init__("RESOURCE_NOT_FOUND", f"{resource}不存在", 404)


class PermissionDeniedError(AppError):
    def __init__(self, message: str = "无权执行此操作"):
        super().__init__("PERMISSION_DENIED", message, 403)

