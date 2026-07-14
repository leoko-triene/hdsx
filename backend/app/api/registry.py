"""API feature router registry.

新增后端功能时，在 app/api/features/ 下创建一个包含 APIRouter 的模块，
并在该模块顶部调用 register_feature_router(router)。
最后在本文件底部通过 `from .features import <feature>` 触发模块加载即可。
"""

from fastapi import APIRouter

_feature_routers: list[APIRouter] = []


def register_feature_router(router: APIRouter) -> APIRouter:
    """注册一个 feature router。返回 router 以便链式调用。"""
    _feature_routers.append(router)
    return router


def get_feature_routers() -> list[APIRouter]:
    """获取所有已注册的 feature router。"""
    return list(_feature_routers)


# 触发 feature 模块加载（按字母顺序导入，避免循环依赖）
from .features import document_export  # noqa: E402, F401
