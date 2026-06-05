"""JSON-RPC message protocol definitions for the mutation testing system.

Defines the message types, error codes, and serialization format for
communication between the mutation testing client and server.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
import json


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Custom error codes for mutation testing
MUTATION_ERROR = -32000
TEST_ERROR = -32001
STATUS_ERROR = -32002
SHUTDOWN_ERROR = -32003


# Supported methods
METHOD_RUN_MUTATION = "run_mutation"
METHOD_RUN_TEST = "run_test"
METHOD_GET_STATUS = "get_status"
METHOD_SHUTDOWN = "shutdown"


@dataclass
class JsonRpcRequest:
    """A JSON-RPC request message."""
    id: Union[int, str]
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
        }
        if self.params is not None:
            result["params"] = self.params
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcRequest":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            method=data["method"],
            params=data.get("params"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "JsonRpcRequest":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class JsonRpcError:
    """A JSON-RPC error object."""
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcError":
        """Create from dictionary."""
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data"),
        )


@dataclass
class JsonRpcResponse:
    """A JSON-RPC response message."""
    id: Union[int, str, None]
    result: Optional[Any] = None
    error: Optional[JsonRpcError] = None
    jsonrpc: str = "2.0"

    def __post_init__(self):
        """Validate that exactly one of result or error is set."""
        if self.result is not None and self.error is not None:
            raise ValueError("Response cannot have both result and error")
        if self.result is None and self.error is None:
            raise ValueError("Response must have either result or error")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.error is not None:
            result["error"] = self.error.to_dict()
        else:
            result["result"] = self.result
        return result

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcResponse":
        """Create from dictionary."""
        error = None
        if "error" in data:
            error = JsonRpcError.from_dict(data["error"])
        return cls(
            id=data["id"],
            result=data.get("result"),
            error=error,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "JsonRpcResponse":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def success(cls, id: Union[int, str, None], result: Any) -> "JsonRpcResponse":
        """Create a successful response."""
        return cls(id=id, result=result)

    @classmethod
    def failure(cls, id: Union[int, str, None], code: int, message: str, data: Any = None) -> "JsonRpcResponse":
        """Create an error response."""
        return cls(id=id, error=JsonRpcError(code=code, message=message, data=data))


# Convenience functions for creating requests

def create_run_mutation_request(id: Union[int, str], params: Dict[str, Any]) -> JsonRpcRequest:
    """Create a run_mutation request.

    Expected params:
        - mutation_id: str
        - source_file: str
        - mutation_type: str
        - line: int
        - original_code: str
        - mutated_code: str
    """
    return JsonRpcRequest(id=id, method=METHOD_RUN_MUTATION, params=params)


def create_run_test_request(id: Union[int, str], params: Dict[str, Any]) -> JsonRpcRequest:
    """Create a run_test request.

    Expected params:
        - test_file: str
        - test_name: str
        - mutation_id: str (optional)
    """
    return JsonRpcRequest(id=id, method=METHOD_RUN_TEST, params=params)


def create_get_status_request(id: Union[int, str]) -> JsonRpcRequest:
    """Create a get_status request."""
    return JsonRpcRequest(id=id, method=METHOD_GET_STATUS)


def create_shutdown_request(id: Union[int, str]) -> JsonRpcRequest:
    """Create a shutdown request."""
    return JsonRpcRequest(id=id, method=METHOD_SHUTDOWN)


# Error message helpers

def method_not_found_error(id: Union[int, str, None], method: str) -> JsonRpcResponse:
    """Create a method not found error response."""
    return JsonRpcResponse.failure(
        id=id,
        code=METHOD_NOT_FOUND,
        message=f"Method '{method}' not found",
    )


def invalid_params_error(id: Union[int, str, None], message: str) -> JsonRpcResponse:
    """Create an invalid params error response."""
    return JsonRpcResponse.failure(
        id=id,
        code=INVALID_PARAMS,
        message=message,
    )


def internal_error(id: Union[int, str, None], message: str = "Internal error") -> JsonRpcResponse:
    """Create an internal error response."""
    return JsonRpcResponse.failure(
        id=id,
        code=INTERNAL_ERROR,
        message=message,
    )


def parse_error(id: Union[int, str, None] = None) -> JsonRpcResponse:
    """Create a parse error response."""
    return JsonRpcResponse.failure(
        id=id,
        code=PARSE_ERROR,
        message="Parse error",
    )


def invalid_request_error(id: Union[int, str, None] = None) -> JsonRpcResponse:
    """Create an invalid request error response."""
    return JsonRpcResponse.failure(
        id=id,
        code=INVALID_REQUEST,
        message="Invalid request",
    )