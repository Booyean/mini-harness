import re

CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "计算数学表达式的结果，例如 '3+5*2'",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的数学表达式，例如 '3+5*2'",
                }
            },
            "required": ["expression"],
        },
    },
}


def execute_calculator(arguments):
    expression = str(arguments.get("expression", "")).strip()
    if not re.fullmatch(r"[0-9+\-*/().%\s]+", expression):
        return "错误：表达式含有非法字符"
    try:
        result = eval(expression)
    except Exception as e:
        return f"计算失败: {e}"
    return str(result)
