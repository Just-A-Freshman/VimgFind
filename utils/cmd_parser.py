from __future__ import annotations

from dataclasses import dataclass, field
import re


FILE_VARS = frozenset({"path", "paths", "dir", "name", "noext", "ext", "count"})
ASK_VARS = frozenset({"ask_dir", "ask_file", "ask_files", "ask_string", "ask_int", "ask_float"})
LIST_VARS = frozenset({"paths", "ask_files"})
ALL_VARS = FILE_VARS | ASK_VARS

VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SHELL_METACHARS = frozenset({"|", "<", ">", "&"})


@dataclass(frozen=True)
class ParseError:
    line: int
    col: int
    code: str
    message: str


@dataclass(frozen=True)
class ParseResult:
    argv: list[str] | None
    errors: list[ParseError] = field(default_factory=list)
    asks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VarExpr:
    raw: str
    name: str
    sep: str | None
    col: int



def parse(command: str) -> ParseResult:
    tokens, exprs, errors, asks, warnings = _analyze(command)
    return ParseResult(None, errors, asks, warnings)


def resolve(command: str, vars: dict[str, str | list[str]]) -> ParseResult:
    tokens, exprs, errors, asks, warnings = _analyze(command)
    if errors:
        return ParseResult(None, errors, asks, warnings)
    argv: list[str] = []
    for token, token_exprs in zip(tokens, exprs):
        argv.extend(_expand_token(token, token_exprs, vars))
    return ParseResult(argv, [], asks, warnings)


def _analyze(command: str):
    """返回 (tokens, exprs_per_token, errors, asks, warnings)。"""
    raw_lines = [ln.strip() for ln in command.split("\n")]
    exec_lines: list[tuple[int, str]] = []
    for idx, ln in enumerate(raw_lines, start=1):
        if not ln or ln.startswith("#"):
            continue
        exec_lines.append((idx, ln))
    if not exec_lines:
        return [], [], [ParseError(1, 1, "E000", "命令内容为空")], [], []
    if len(exec_lines) > 1:
        line_no = exec_lines[1][0]
        return [], [], [ParseError(line_no, 1, "E001", "命令只允许一行，多步骤请封装到脚本中")], [], []

    line_no, text = exec_lines[0]
    tokens, starts, token_errors = _tokenize(text)
    if token_errors:
        return tokens, [[] for _ in tokens], token_errors, [], []

    exprs_per_token: list[list[VarExpr]] = []
    errors: list[ParseError] = []
    asks: list[str] = []
    warnings: list[str] = []
    for token, start in zip(tokens, starts):
        token_exprs, var_errors = _parse_var_exprs(token, start)
        for e in var_errors:
            errors.append(ParseError(line_no, e.col, e.code, e.message))
        for expr in token_exprs:
            if expr.name in ASK_VARS and expr.name not in asks:
                asks.append(expr.name)
        if not token_exprs and token in SHELL_METACHARS:
            warnings.append(f"参数 `{token}` 将作为普通参数传给程序，不会执行管道/重定向")
        exprs_per_token.append(token_exprs)
    return tokens, exprs_per_token, errors, asks, warnings


def _tokenize(text: str) -> tuple[list[str], list[int], list[ParseError]]:
    tokens: list[str] = []
    starts: list[int] = []
    errors: list[ParseError] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] in " \t":
            i += 1
            continue
        buf: list[str] = []
        token_col = i + 1
        in_quote = False
        quote_col = i + 1
        saw_quote = False
        while i < n:
            c = text[i]
            if not in_quote and c in " \t":
                break
            if c == "\\" and in_quote and i + 1 < n and text[i + 1] in ('"', "\\"):
                buf.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_quote = not in_quote
                saw_quote = True
                i += 1
                continue
            if c == "{":
                j = text.find("}", i)
                if j == -1:
                    errors.append(ParseError(1, i + 1, "E003", "未闭合的变量 `{`，缺少 `}`"))
                    buf.append(text[i:])
                    i = n
                    break
                inner = text[i + 1 : j]
                k = inner.find("{")
                if k != -1:
                    errors.append(ParseError(1, i + k + 2, "E010", "变量/修饰符值中不支持嵌套 `{`"))
                buf.append(text[i : j + 1])
                i = j + 1
                continue
            buf.append(c)
            i += 1
        if in_quote:
            errors.append(ParseError(1, quote_col, "E002", "未闭合的引号 `\"`"))
        if buf or saw_quote:
            tokens.append("".join(buf))
            starts.append(token_col)
    return tokens, starts, errors


def _parse_var_exprs(token: str, token_col: int) -> tuple[list[VarExpr], list[ParseError]]:
    exprs: list[VarExpr] = []
    errors: list[ParseError] = []
    i = 0
    while i < len(token):
        if token[i] != "{":
            i += 1
            continue
        j = token.find("}", i)
        if j == -1:
            break
        raw = token[i : j + 1]
        body = raw[1:-1]
        col = token_col + i
        if not body:
            errors.append(ParseError(1, col, "E004", "变量名为空（{}）"))
        else:
            colon = body.find(":")
            name = body[:colon] if colon != -1 else body
            mod = body[colon + 1 :] if colon != -1 else ""
            err = _validate_var(name, mod, col)
            if err is not None:
                errors.append(err)
            else:
                sep = _unescape_sep(mod[4:]) if mod else None
                exprs.append(VarExpr(raw, name, sep, col))
        i = j + 1
    return exprs, errors


def _validate_var(name: str, mod: str, col: int) -> ParseError | None:
    if not VAR_NAME_RE.match(name):
        return ParseError(1, col, "E006", f"变量名含非法字符：`{name}`")
    if name not in ALL_VARS:
        return ParseError(1, col, "E005", f"未知变量 `{{{name}}}`")
    if mod:
        if not mod.startswith("sep="):
            return ParseError(1, col, "E007", f"未知修饰符 `{mod}`，仅支持 `sep=`")
        if not mod[4:]:
            return ParseError(1, col, "E009", "`sep` 的值不能为空")
        if name not in LIST_VARS:
            return ParseError(1, col, "E008", "`sep` 仅适用于列表变量（paths/ask_files）")
    return None


def _unescape_sep(value: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _expand_token(token: str, exprs: list[VarExpr], vars: dict) -> list[str]:
    if not exprs:
        return [token]
    if len(exprs) == 1 and exprs[0].raw == token:
        expr = exprs[0]
        val = vars[expr.name]
        if isinstance(val, list):
            if expr.sep is not None:
                return [expr.sep.join(val)]
            return list(val)
        return [str(val)]
    result = token
    for expr in exprs:
        val = vars[expr.name]
        if isinstance(val, list):
            repl = expr.sep.join(val) if expr.sep is not None else " ".join(val)
        else:
            repl = str(val)
        result = result.replace(expr.raw, repl, 1)
    return [result]
