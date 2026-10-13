from tools import (
    ask_user,
    calculator,
    download,
    filesystem,
    search,
    shell,
    subagent,
    todo,
    vision,
)

TOOL_EXECUTORS = {
    "calculator": calculator.execute_calculator,
    "read_file": filesystem.execute_read_file,
    "list_files": filesystem.execute_list_files,
    "delete_file": filesystem.execute_delete_file,
    "write_file": filesystem.execute_write_file,
    "edit_file": filesystem.execute_edit_file,
    "run_bash": shell.execute_run_bash,
    "web_search": search.execute_web_search,
    "grep": search.execute_grep,
    "webfetch": search.execute_webfetch,
    "update_todo": todo.execute_update_todo,
    "run_subtask": subagent.execute_run_subtask,
    "ask_user": ask_user.execute_ask_user,
    "download_file": download.execute_download_file,
    "read_image": vision.execute_read_image,
    "ocr_image": vision.execute_ocr_image,
}


_dynamic_executors = {}
_dynamic_schemas = []


def register_dynamic(name, executor, schema):
    _dynamic_executors[name] = executor
    _dynamic_schemas.append(schema)


def get_tool_schemas():
    return [
        calculator.CALCULATOR_TOOL,
        filesystem.READ_FILE_TOOL,
        filesystem.LIST_FILES_TOOL,
        filesystem.DELETE_FILE_TOOL,
        filesystem.WRITE_FILE_TOOL,
        filesystem.EDIT_FILE_TOOL,
        shell.RUN_BASH_TOOL,
        search.WEB_SEARCH_TOOL,
        search.GREP_TOOL,
        search.WEBFETCH_TOOL,
        todo.UPDATE_TODO_TOOL,
        subagent.RUN_SUBTASK_TOOL,
        ask_user.ASK_USER_TOOL,
        download.DOWNLOAD_TOOL,
        vision.READ_IMAGE_TOOL,
        vision.OCR_IMAGE_TOOL,
    ] + _dynamic_schemas


def execute_tool(name, arguments):
    executor = TOOL_EXECUTORS.get(name) or _dynamic_executors.get(name)
    if executor is None:
        return f"未知工具: {name}"
    return executor(arguments)
