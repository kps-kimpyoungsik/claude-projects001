"""[Phase 3.1] Deterministic 추출기 — Python AST 기반 함수/호출 관계.

설계 명세: "코드 분석(AST)을 통해 함수 간 관계는 로컬에서 100% 추출"
LLM 호출 없이 표준 라이브러리 `ast`만 사용 — confidence는 항상 1.0(결정론적).
"""

import ast

from backend.domain.graph.entities import Edge, EdgeKind, Node, NodeKind


def extract_functions_and_calls(source: str, source_path: str) -> tuple[list[Node], list[Edge]]:
    """단일 Python 소스에서 함수 정의(Node)와 함수 호출 관계(Edge, CALLS)를 추출한다.

    범위(의도적 단순화, 스캐폴딩 단계):
    - 모듈 최상위 + 클래스 메서드의 `def` 만 Function 노드로 취급.
    - 호출 대상 이름 해석은 문자열 매칭 수준(동일 모듈 내 정의된 함수명만 매칭) —
      import된 외부 함수·동적 디스패치는 다루지 않는다(과장 금지, T98 AIP).
    """
    tree = ast.parse(source, filename=source_path)

    nodes: list[Node] = []
    defined_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node_id = f"{source_path}::{node.name}:{node.lineno}"
            nodes.append(
                Node(
                    node_id=node_id,
                    kind=NodeKind.FUNCTION,
                    label=node.name,
                    source_ref=f"{source_path}:{node.lineno}",
                )
            )
            defined_names.add(node.name)

    edges: list[Edge] = []
    func_stack: list[str] = []

    class CallVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef):  # noqa: N802
            func_stack.append(f"{source_path}::{node.name}:{node.lineno}")
            self.generic_visit(node)
            func_stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_Call(self, node: ast.Call):  # noqa: N802
            if func_stack and isinstance(node.func, ast.Name) and node.func.id in defined_names:
                caller_id = func_stack[-1]
                # 대상 노드 id는 이름만으로 유일 결정 불가할 수 있어(오버로드 없음 가정)
                # 첫 매칭 노드로 연결한다 — 다중 정의 시 부정확할 수 있음(스캐폴딩 한계).
                target = next((n.node_id for n in nodes if n.label == node.func.id), None)
                if target and target != caller_id:
                    edges.append(
                        Edge(
                            edge_id=f"{caller_id}->{target}",
                            kind=EdgeKind.CALLS,
                            source_id=caller_id,
                            target_id=target,
                            confidence=1.0,
                        )
                    )
            self.generic_visit(node)

    CallVisitor().visit(tree)
    return nodes, edges
