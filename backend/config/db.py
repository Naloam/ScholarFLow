from __future__ import annotations

from functools import cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import settings


@cache
def get_session_factory():
    """首次调用时才创建 engine 与 session 工厂（每进程一次）。

    模块级 ``create_engine(settings.database_url)`` 会在 **import 时**就解析
    ``postgresql://`` 方言的 DBAPI（psycopg）。CI 的测试环境没有该驱动，
    于是任何间接 import 本模块的测试文件都在收集阶段直接
    ``ModuleNotFoundError`` —— 2026-10 起 master 的 6 个测试文件因此红着。
    引擎推迟到第一次真实建会话时才创建；应用与 e2e 脚本运行环境装有
    psycopg，行为不变。"""
    engine = create_engine(settings.database_url, future=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def __getattr__(name: str):
    """兼容 ``from config.db import engine / SessionLocal`` 的旧写法，且保持惰性。"""
    if name == "SessionLocal":
        return get_session_factory()
    if name == "engine":
        return get_session_factory().kw["bind"]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
