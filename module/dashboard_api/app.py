from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from module.dashboard_api.auth import require_admin, require_user
from module.dashboard_api.config import load_api_config
from module.dashboard_api.db import Database
from module.dashboard_api.models import ApiUserCreateRequest, ApiUserTokenResponse, ApiUserUpdateRequest, PushRequest, ResourceLatestListResponse
from module.dashboard_api.service import DashboardService


def _json_error(message, status_code=400):
    return JSONResponse({"error": message}, status_code=status_code)


async def _http_exception_handler(request, exc):
    return _json_error(exc.detail, status_code=exc.status_code)


async def _read_model(request: Request, model_cls):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    try:
        return model_cls.parse_obj(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors())


async def health(request: Request):
    return JSONResponse(request.app.state.service.health())


async def admin_list_users(request: Request):
    require_admin(request)
    users = [user.dict() for user in request.app.state.service.list_users()]
    return JSONResponse({"users": users})


async def admin_create_user(request: Request):
    require_admin(request)
    payload = await _read_model(request, ApiUserCreateRequest)
    try:
        user, token = request.app.state.service.create_user(
            user_key=payload.user_key,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return _json_error(str(exc), status_code=409)
    response = ApiUserTokenResponse(user=user, token=token)
    return JSONResponse(response.dict(), status_code=201)


async def admin_get_user(request: Request):
    require_admin(request)
    user = request.app.state.service.get_user(int(request.path_params["user_id"]))
    if user is None:
        return _json_error("User not found", status_code=404)
    return JSONResponse(user.dict())


async def admin_patch_user(request: Request):
    require_admin(request)
    payload = await _read_model(request, ApiUserUpdateRequest)
    user = request.app.state.service.update_user(
        int(request.path_params["user_id"]),
        display_name=payload.display_name,
        is_active=payload.is_active,
    )
    if user is None:
        return _json_error("User not found", status_code=404)
    return JSONResponse(user.dict())


async def admin_rotate_user_token(request: Request):
    require_admin(request)
    rotated = request.app.state.service.rotate_token(int(request.path_params["user_id"]))
    if rotated is None:
        return _json_error("User not found", status_code=404)
    user, token = rotated
    return JSONResponse(ApiUserTokenResponse(user=user, token=token).dict())


async def get_me(request: Request):
    user = require_user(request)
    return JSONResponse(request.app.state.service.serialize_user(user).dict())


async def create_push(request: Request):
    user = require_user(request)
    payload = await _read_model(request, PushRequest)
    try:
        result = request.app.state.service.store_push(user, payload)
    except ValueError as exc:
        return _json_error(str(exc), status_code=400)
    return JSONResponse(result, status_code=202)


async def get_latest_resources(request: Request):
    user = require_user(request)
    resources = request.app.state.service.get_latest_resources(user.id)
    return JSONResponse(ResourceLatestListResponse(resources=resources).dict())


async def get_resource_history(request: Request):
    user = require_user(request)
    query = request.query_params
    try:
        from_ms = int(query["from_ms"]) if "from_ms" in query else None
        to_ms = int(query["to_ms"]) if "to_ms" in query else None
        limit = int(query.get("limit", 500))
    except ValueError:
        return _json_error("from_ms, to_ms and limit must be integers", status_code=400)
    limit = max(1, min(limit, 5000))
    order = query.get("order", "desc")
    if order not in {"asc", "desc"}:
        return _json_error("order must be asc or desc", status_code=400)
    try:
        resources = request.app.state.service.get_resource_history(
            user.id,
            request.path_params["resource_name"],
            from_ms,
            to_ms,
            limit,
            order,
        )
    except ValueError as exc:
        return _json_error(str(exc), status_code=400)
    return JSONResponse({"resource_name": request.path_params["resource_name"], "items": [item.dict() for item in resources]})


async def get_widget_overview(request: Request):
    user = require_user(request)
    return JSONResponse(request.app.state.service.get_widget_overview(user.id).dict())


def create_app(config_path: str):
    api_config = load_api_config(config_path)
    database = Database(api_config.database_url)
    database.create_all()
    service = DashboardService(database)

    middleware = []
    if api_config.cors_allowed_origins:
        middleware.append(
            Middleware(
                CORSMiddleware,
                allow_origins=api_config.cors_allowed_origins,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        )

    app = Starlette(
        debug=False,
        middleware=middleware,
        exception_handlers={HTTPException: _http_exception_handler},
        routes=[
            Route("/api/v1/health", health, methods=["GET"]),
            Route("/api/v1/admin/users", admin_list_users, methods=["GET"]),
            Route("/api/v1/admin/users", admin_create_user, methods=["POST"]),
            Route("/api/v1/admin/users/{user_id:int}", admin_get_user, methods=["GET"]),
            Route("/api/v1/admin/users/{user_id:int}", admin_patch_user, methods=["PATCH"]),
            Route("/api/v1/admin/users/{user_id:int}/rotate-token", admin_rotate_user_token, methods=["POST"]),
            Route("/api/v1/me", get_me, methods=["GET"]),
            Route("/api/v1/pushes", create_push, methods=["POST"]),
            Route("/api/v1/resources/latest", get_latest_resources, methods=["GET"]),
            Route("/api/v1/resources/{resource_name:str}/history", get_resource_history, methods=["GET"]),
            Route("/api/v1/widget/overview", get_widget_overview, methods=["GET"]),
        ],
    )
    app.state.api_config = api_config
    app.state.service = service
    return app
