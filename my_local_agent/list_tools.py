import ast

with open("tools/agent_tools.py", "r") as f:
    tree = ast.parse(f.read())

for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if getattr(decorator, 'id', None) == 'tool' or (isinstance(decorator, ast.Call) and getattr(decorator.func, 'id', None) == 'tool'):
                print(f"- **{node.name}**: {ast.get_docstring(node).splitlines()[0] if ast.get_docstring(node) else 'N/A'}")
