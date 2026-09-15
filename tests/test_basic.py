import ast
from pathlib import Path


LAMBDA_DIR = Path(__file__).resolve().parent.parent / "lambda"

LAMBDA_FUNCTIONS = [
    "deleteDocument",
    "downloadDocument",
    "listDocuments",
    "uploadDocument",
]


def test_lambda_files_exist():
    """Verify that all four Lambda source files exist."""

    for function_name in LAMBDA_FUNCTIONS:
        file_path = LAMBDA_DIR / function_name / "lambda_function.py"

        assert file_path.exists(), (
            f"Missing Lambda file: {file_path}"
        )


def test_lambda_files_have_valid_syntax():
    """Verify that all Lambda files contain valid Python syntax."""

    for function_name in LAMBDA_FUNCTIONS:
        file_path = LAMBDA_DIR / function_name / "lambda_function.py"

        source = file_path.read_text(encoding="utf-8")

        # ast.parse checks Python syntax without executing the Lambda
        ast.parse(source, filename=str(file_path))


def test_lambda_handlers_exist():
    """Verify that every Lambda file defines lambda_handler."""

    for function_name in LAMBDA_FUNCTIONS:
        file_path = LAMBDA_DIR / function_name / "lambda_function.py"

        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        functions = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        assert "lambda_handler" in functions, (
            f"lambda_handler not found in {file_path}"
        )