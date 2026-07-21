"""Gemini function tools for Companion watchlist agent."""

from __future__ import annotations

from google.genai import types

WATCHLIST_TOOL_INSTRUCTION = """

Công cụ danh sách theo dõi (BẮT BUỘC khi user muốn thay đổi watchlist):
- User muốn tạo list/danh sách mới → gọi create_watchlist (kèm symbols hoặc sector).
- User muốn thêm mã vào list cụ thể → gọi add_symbol_to_watchlist.
- XÓA mã — phân biệt rõ:
  · User nói chung ("xóa mã kém", "list cồng kềnh", "tái cấu trúc"): KHÔNG gọi remove.
    Hãy gợi ý cụ thể N mã + lý do ngắn (dựa list/context), hỏi user đồng ý trước.
  · Chỉ gọi remove_symbol_from_watchlist KHI user đã chỉ rõ mã (vd. xóa VCB, FPT)
    HOẶC đã đồng ý gợi ý trước đó ("ok", "đồng ý", "xóa mấy mã đó").
  · Một mã: symbol. Nhiều mã: symbols[]. Không gọi suggest_add khi đang xóa.
- Câu hỏi trạng thái ("xóa xong chưa?", "còn bao nhiêu mã?"): KHÔNG gọi function;
  trả lời thẳng từ [Danh sách theo dõi của user].
- User đồng ý thêm mã bạn vừa gợi ý → gọi add_symbol_to_watchlist hoặc suggest_add_symbol.
- App CHỈ hiện pop-up khi bạn gọi function — đừng nói "xác nhận trên pop-up" nếu chưa gọi.
- Vẫn trả lời ngắn bằng lời nói; gọi function song song khi cần hành động.
- symbols phải là mã CK 3 chữ cái hợp lệ từ context; sector: bank | securities | real_estate | energy.
"""


def watchlist_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="create_watchlist",
                    description=(
                        "Đề xuất tạo danh sách theo dõi mới. "
                        "Gọi khi user muốn tạo/làm list mới theo ngành hoặc tên tùy chỉnh."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        required=["name"],
                        properties={
                            "name": types.Schema(
                                type=types.Type.STRING,
                                description="Tên danh sách, vd. Ngân hàng, Năng lượng",
                            ),
                            "symbols": types.Schema(
                                type=types.Type.ARRAY,
                                description="Mã CK ban đầu (3 chữ cái), tối đa 12",
                                items=types.Schema(type=types.Type.STRING),
                            ),
                            "sector": types.Schema(
                                type=types.Type.STRING,
                                description="bank | securities | real_estate | energy",
                            ),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="add_symbol_to_watchlist",
                    description=(
                        "Đề xuất thêm một mã vào danh sách đã có. "
                        "Gọi khi user muốn thêm mã hoặc đồng ý thêm mã vừa bàn."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        required=["symbol"],
                        properties={
                            "symbol": types.Schema(
                                type=types.Type.STRING,
                                description="Mã CK 3 chữ cái, vd. VCB",
                            ),
                            "watchlist_name": types.Schema(
                                type=types.Type.STRING,
                                description="Tên list đích, khớp với [Danh sách theo dõi của user]",
                            ),
                            "watchlist_id": types.Schema(
                                type=types.Type.STRING,
                                description="ID list nếu biết từ context",
                            ),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="remove_symbol_from_watchlist",
                    description=(
                        "Đề xuất xóa một hoặc nhiều mã khỏi danh sách đã có. "
                        "Gọi khi user muốn xóa/gỡ/bỏ mã khỏi list. "
                        "Dùng symbols khi xóa nhiều mã cùng lúc."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "symbol": types.Schema(
                                type=types.Type.STRING,
                                description="Một mã CK 3 chữ cái cần xóa (khi chỉ xóa 1 mã)",
                            ),
                            "symbols": types.Schema(
                                type=types.Type.ARRAY,
                                description="Nhiều mã CK cần xóa cùng lúc (tối đa 8)",
                                items=types.Schema(type=types.Type.STRING),
                            ),
                            "watchlist_name": types.Schema(
                                type=types.Type.STRING,
                                description="Tên list nguồn, khớp [Danh sách theo dõi của user]",
                            ),
                            "watchlist_id": types.Schema(
                                type=types.Type.STRING,
                                description="ID list nếu biết từ context",
                            ),
                        },
                    ),
                ),
                types.FunctionDeclaration(
                    name="suggest_add_symbol",
                    description=(
                        "Chủ động đề xuất thêm mã user đang quan tâm vào watchlist "
                        "(khi user hỏi nhiều về mã chưa có trong list)."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        required=["symbol"],
                        properties={
                            "symbol": types.Schema(type=types.Type.STRING),
                            "reason": types.Schema(type=types.Type.STRING),
                        },
                    ),
                ),
            ],
        )
    ]


def watchlist_tool_config() -> types.ToolConfig:
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.AUTO,
        ),
    )


def extract_function_calls(response) -> list[dict]:
    """Parse Gemini response into [{name, args}, ...]."""
    out: list[dict] = []
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return out
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    for part in parts:
        fc = getattr(part, "function_call", None)
        if not fc or not fc.name:
            continue
        raw_args = fc.args
        if raw_args is None:
            args: dict = {}
        elif isinstance(raw_args, dict):
            args = dict(raw_args)
        else:
            try:
                args = dict(raw_args)
            except (TypeError, ValueError):
                args = {}
        out.append({"name": str(fc.name), "args": args})
    return out
