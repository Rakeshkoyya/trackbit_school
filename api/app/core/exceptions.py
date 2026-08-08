"""Application error hierarchy + FastAPI handlers.

Services raise these; the handlers translate them to consistent JSON. Endpoints
should not raise HTTPException directly for business errors.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        self.message = message
        if code:
            self.code = code
        self.details = details or {}
        super().__init__(message)


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, resource: str, identifier: str = ""):
        msg = f"{resource} not found" + (f": {identifier}" if identifier else "")
        super().__init__(msg)


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class PlanLimitError(AppError):
    """The school's plan does not include this feature. Never silent — carries
    a structured upgrade prompt the client renders. 402 Payment Required.

    `required_tier` is what makes the prompt actionable (`D-106`): the wall can
    name the tier and quote this school's own price rather than saying
    "upgrade" and leaving them to work out which one. Raised from
    `core/features.py::require_feature`, which should be the only thing that
    constructs it.
    """

    status_code = 402
    code = "plan_limit"

    def __init__(
        self,
        feature: str,
        *,
        required_tier: str,
        message: str,
        feature_label: str = "",
    ):
        super().__init__(
            message,
            details={
                "feature": feature,
                "feature_label": feature_label or feature,
                "required_tier": required_tier,
                "upgrade": True,
            },
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
