"""Framework-agnostic Tool Registry for the Agentic dbt Harness."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, create_model


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: Any = None  # Callable reference
    return_type_desc: Optional[str] = None


class ToolRegistry:
    """Stores and exposes domain tools independently of any specific agent runtime."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        schema_model: type[BaseModel] | None = None,
    ) -> None:
        """Register a Python callable as an agent tool."""
        if schema_model is not None:
            json_schema = schema_model.model_json_schema()
        else:
            # Build schema dynamically from type annotations if not explicitly passed
            json_schema = self._build_schema_from_func(handler)

        doc = description or (inspect.getdoc(handler) or "").strip()
        tool_def = ToolDefinition(
            name=name,
            description=doc,
            parameters_schema=json_schema,
            handler=handler,
        )
        self._tools[name] = tool_def

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def execute(self, tool_name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(tool_name)
        if not tool:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        if not callable(tool.handler):
            raise TypeError(f"Handler for tool '{tool_name}' is not callable.")
        return tool.handler(**kwargs)

    @staticmethod
    def _build_schema_from_func(fn: Callable[..., Any]) -> Dict[str, Any]:
        sig = inspect.signature(fn)
        fields: Dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else Any
            default = param.default if param.default != inspect.Parameter.empty else ...
            fields[param_name] = (annotation, default)

        dyn_model = create_model(f"{fn.__name__}_args", **fields)
        return dyn_model.model_json_schema()

