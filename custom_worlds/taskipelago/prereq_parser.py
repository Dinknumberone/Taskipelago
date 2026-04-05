"""
Boolean prereq expression parser for Taskipelago.

Grammar:
    expr     := or_expr
    or_expr  := and_expr ('||' and_expr)*
    and_expr := atom ('&&' atom | ',' atom)*
    atom     := INTEGER | '(' expr ')'

Output AST nodes:
    int                    - leaf: require this task index (0-based)
    ("and", [node, ...])   - all children must be satisfied
    ("or",  [node, ...])   - at least one child must be satisfied

A single-child "and" or "or" is simplified to just the child.
"""
from __future__ import annotations
from typing import List, Tuple, Union

# AST node type
Node = Union[int, Tuple[str, list]]


def parse_prereq(text: str, n_tasks: int, task_index: int, label: str) -> Node | None:
    """
    Parse a prereq expression string into an AST.
    Returns None if the expression is empty.
    Raises Exception on syntax or range errors.
    All returned leaf values are 0-based task indices.
    """
    text = text.strip()
    if not text:
        return None

    tokens = _tokenize(text, task_index, label)
    if not tokens:
        return None

    pos = [0]  # mutable so nested functions can advance it

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def consume(expected=None):
        tok = tokens[pos[0]]
        if expected is not None and tok != expected:
            raise Exception(
                f"Taskipelago: expected '{expected}' but got '{tok}' "
                f"in {label} on task {task_index + 1}."
            )
        pos[0] += 1
        return tok

    def parse_expr():
        return parse_or()

    def parse_or():
        left = parse_and()
        nodes = [left]
        while peek() == "||":
            consume("||")
            nodes.append(parse_and())
        return _simplify("or", nodes)

    def parse_and():
        left = parse_atom()
        nodes = [left]
        while peek() in ("&&", ","):
            consume()  # consume && or ,
            nodes.append(parse_atom())
        return _simplify("and", nodes)

    def parse_atom():
        tok = peek()
        if tok is None:
            raise Exception(
                f"Taskipelago: unexpected end of {label} expression on task {task_index + 1}."
            )
        if tok == "(":
            consume("(")
            node = parse_expr()
            consume(")")
            return node
        if isinstance(tok, int):
            consume()
            idx_1 = tok
            if idx_1 < 1 or idx_1 > n_tasks:
                raise Exception(
                    f"Taskipelago: {label} index '{idx_1}' on task {task_index + 1} "
                    f"is out of range (1..{n_tasks})."
                )
            return idx_1 - 1  # 0-based
        raise Exception(
            f"Taskipelago: unexpected token '{tok}' in {label} on task {task_index + 1}."
        )

    result = parse_expr()

    if pos[0] != len(tokens):
        raise Exception(
            f"Taskipelago: unexpected token '{tokens[pos[0]]}' in {label} on task {task_index + 1}."
        )

    return result


def _simplify(op: str, nodes: list) -> Node:
    """Flatten single-child and/or nodes."""
    if len(nodes) == 1:
        return nodes[0]
    return (op, nodes)


def _tokenize(text: str, task_index: int, label: str) -> list:
    """
    Convert expression string into a flat list of tokens:
    integers, '(', ')', '&&', '||', ','
    """
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]

        if c.isspace():
            i += 1
            continue

        if c.isdigit():
            j = i
            while j < len(text) and text[j].isdigit():
                j += 1
            tokens.append(int(text[i:j]))
            i = j
            continue

        if text[i:i+2] == "&&":
            tokens.append("&&")
            i += 2
            continue

        if text[i:i+2] == "||":
            tokens.append("||")
            i += 2
            continue

        if c in ("(", ")", ","):
            tokens.append(c)
            i += 1
            continue

        raise Exception(
            f"Taskipelago: unexpected character '{c}' in {label} on task {task_index + 1}."
        )

    return tokens


def collect_leaves(node: Node | None) -> List[int]:
    """Return all 0-based task indices referenced in an AST node."""
    if node is None:
        return []
    if isinstance(node, int):
        return [node]
    _, children = node
    result = []
    for child in children:
        result.extend(collect_leaves(child))
    return result


def eval_node(node: Node | None, state, player: int, item_names: List[str]) -> bool:
    """
    Evaluate an AST node against a CollectionState.
    item_names: list of item name strings indexed by 0-based task index.
    """
    if node is None:
        return True
    if isinstance(node, int):
        return state.has(item_names[node], player)
    op, children = node
    if op == "and":
        return all(eval_node(child, state, player, item_names) for child in children)
    if op == "or":
        return any(eval_node(child, state, player, item_names) for child in children)
    raise ValueError(f"Unknown AST op: {op}")

def _has_or(node: Node | None) -> bool:
    """Return True if any OR node exists in the AST."""
    if node is None or isinstance(node, int):
        return False
    op, children = node
    if op == "or":
        return True
    return any(_has_or(child) for child in children)