"""分层依赖守卫（设计文档 §3.1）。

设计文档承诺 `application → infrastructure via abstract ports`。该承诺一旦没有
测试兜底，就会像这次改造前一样悄悄退化成「application 直接 import 具体实现」。
本模块把依赖方向固化成断言。

允许的方向：

```
domain          → （不依赖任何其他层）
application     → domain
infrastructure  → domain, application（实现 application 定义的端口）
interfaces      → domain, application
```

唯一豁免是 `application/container.py`：组合根的职责就是知道具体实现并完成装配。
"""
import ast
import pathlib
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LAYERS = ("domain", "application", "infrastructure", "interfaces")

ALLOWED = {
    "domain": frozenset(),
    "application": frozenset({"domain"}),
    "infrastructure": frozenset({"domain", "application"}),
    "interfaces": frozenset({"domain", "application"}),
}

#: 组合根：唯一被允许直接依赖 infrastructure 的 application 模块。
COMPOSITION_ROOT = "application/container.py"


def _collect_modules() -> dict:
    modules = {}
    for layer in LAYERS:
        for path in pathlib.Path(REPO_ROOT, layer).rglob("*.py"):
            modules[path.relative_to(REPO_ROOT)] = layer
    return modules


MODULES = _collect_modules()


def _layer_of(module_name: str):
    """把点分模块名解析成所属层；同时支持模块文件与包目录。"""
    base = REPO_ROOT / pathlib.Path(*module_name.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        try:
            key = candidate.relative_to(REPO_ROOT)
        except ValueError:
            return None
        if key in MODULES:
            return MODULES[key]
    return None


def _imported_modules(path: pathlib.Path):
    """产出 `(行号, 模块名)`；只取绝对导入，相对导入天然不跨层。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module


class LayeringTests(unittest.TestCase):
    def test_layers_only_depend_inward(self):
        violations = []
        for relative_path, layer in sorted(MODULES.items()):
            for lineno, module_name in _imported_modules(REPO_ROOT / relative_path):
                target = _layer_of(module_name)
                # 同层导入不是跨层依赖；非本仓库模块（标准库/第三方）同样跳过。
                if target is None or target == layer:
                    continue
                if target in ALLOWED[layer]:
                    continue
                if str(relative_path).replace("\\", "/") == COMPOSITION_ROOT:
                    continue
                violations.append(
                    f"{relative_path}:{lineno}  {layer} -> {target}  ({module_name})"
                )

        self.assertEqual(
            violations, [],
            "跨层依赖违反分层约束（只允许 application/container.py 直接依赖 "
            "infrastructure）：\n  " + "\n  ".join(violations),
        )

    def test_repository_ports_live_in_application_layer(self):
        """端口必须定义在 application 层，否则依赖倒置只做了一半。"""
        self.assertEqual(_layer_of("application.ports.repositories"), "application")
        ports_source = (REPO_ROOT / "application/ports/repositories.py").read_text(encoding="utf-8")
        for port in ("OrderRepository", "BlackboardRepository",
                     "TaskRepository", "MessageRepository"):
            self.assertIn(f"class {port}(ABC)", ports_source,
                          f"{port} 必须定义在 application/ports/repositories.py")

    def test_order_manager_does_not_reach_into_infrastructure(self):
        """OrderManager 只依赖端口；它曾直接 import 4 个 Postgres 与 4 个内存实现。"""
        path = REPO_ROOT / "application/services/order_manager.py"
        imported_layers = {
            _layer_of(module_name)
            for _, module_name in _imported_modules(path)
        }
        self.assertNotIn("infrastructure", imported_layers)


if __name__ == "__main__":
    unittest.main()
