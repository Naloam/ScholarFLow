"""config.db 惰性初始化的回归测试。

背景：模块级 create_engine 曾让任何间接 import config.db 的测试文件
在无 psycopg 的环境（CI）收集阶段直接 ModuleNotFoundError，master 的
测试自 2026-10 起一直红。修复后 import 必须零副作用。
"""

import importlib

import pytest


def test_import_config_db_has_no_side_effect() -> None:
    # 在 CI（无 psycopg）里，这一行 import 在修复前就会抛
    # ModuleNotFoundError —— 修复后收集阶段不再触碰引擎。
    module = importlib.import_module("config.db")
    assert callable(module.get_session_factory)


def test_get_session_factory_is_cached_per_process() -> None:
    module = importlib.import_module("config.db")
    try:
        first = module.get_session_factory()
    except ModuleNotFoundError:
        pytest.skip("DB driver not installed here (CI) — laziness already proven by import success")
    assert first is module.get_session_factory()
