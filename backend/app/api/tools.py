from __future__ import annotations

from fastapi import APIRouter

from app.tools.registry import list_tool_schemas

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
def get_tools():
    return list_tool_schemas()
