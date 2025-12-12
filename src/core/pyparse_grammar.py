"""
Pyparsing tabanlı Ren'Py grammar: diyalog, triple-quote, menu, screen extraction
"""
from typing import List, Dict


def extract_with_pyparsing(content: str, file_path: str = "") -> List[Dict]:
    """
    Gelişmiş pyparsing tabanlı Ren'Py grammar:
    - State machine ve indentation ile blok takibi
    - Triple-quoted monolog bölme (SDK uyumlu)
    - Menü, python, screen, label için ayrı kurallar
    - Placeholder ve stil etiketi koruma
    - Satır devamı ve logical line birleştirme
    - Teknik satırları hariç tutma
    """
    try:
        from pyparsing import (
            Word, alphas, alphanums, quotedString, dblQuotedString, sglQuotedString,
            Suppress, Optional, Group, restOfLine, ParserElement, Regex, LineEnd, LineStart, Combine, OneOrMore, ZeroOrMore, pythonStyleComment, ParseException
        )
        ParserElement.setDefaultWhitespaceChars(' \t')
    except Exception:
        return []

    import re
    entries = []
    # Satır devamı ve logical line birleştirme
    logical_lines = []
    buffer = ""
    for line in content.splitlines():
        if line.rstrip().endswith("\\"):
            buffer += line.rstrip()[:-1] + " "
            continue
        if buffer:
            line = buffer + line
            buffer = ""
        logical_lines.append(line)

    # Teknik satırları hariç tutan anahtar kelimeler
    TECHNICAL_PREFIXES = ("image ", "define ", "default ", "transform ", "style ", "config.", "gui.", "store.", "layout.")

    # Placeholder ve stil etiketi koruma fonksiyonu
    def protect_placeholders(text):
        # [player], {b}, {color=#fff} gibi yapıları maskele
        var_pat = re.compile(r'\[[^\[\]]+\]')
        tag_pat = re.compile(r'\{[^{}]+\}')
        placeholders = {}
        counter = 0
        def repl(m):
            nonlocal counter
            key = f"__PH_{counter}__"
            placeholders[key] = m.group(0)
            counter += 1
            return key
        protected = var_pat.sub(repl, text)
        protected = tag_pat.sub(repl, protected)
        return protected, placeholders

    def restore_placeholders(text, placeholders):
        for k, v in placeholders.items():
            text = text.replace(k, v)
        return text

    state = "INIT"
    indent_stack = [0]
    triple_quote_pat = re.compile(r'(["\']{3})([\s\S]*?)(\1)', re.DOTALL)
    for idx, line in enumerate(logical_lines):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        # Teknik satırları atla
        if not stripped or stripped.startswith("#") or any(stripped.startswith(p) for p in TECHNICAL_PREFIXES):
            continue
        # State değişimi: label, menu, python, screen
        if stripped.startswith("label "):
            state = "LABEL"
            indent_stack.append(indent)
            continue
        elif stripped.startswith("menu"):
            state = "MENU"
            indent_stack.append(indent)
            continue
        elif stripped.startswith("python") or stripped.startswith("$"):
            state = "PYTHON"
            indent_stack.append(indent)
            continue
        elif stripped.startswith("screen "):
            state = "SCREEN"
            indent_stack.append(indent)
            continue
        # Blok sonu
        while indent_stack and indent < indent_stack[-1]:
            indent_stack.pop()
            if len(indent_stack) == 1:
                state = "INIT"

        # Triple-quoted monologue (SDK uyumlu bölme)
        if '"""' in stripped or "'''" in stripped:
            for m in triple_quote_pat.finditer(stripped):
                monologue = m.group(2)
                # SDK gibi: iki yeni satırda böl ve her paragrafı ayrı entry yap
                for para in monologue.split("\n\n"):
                    para = para.strip()
                    if para:
                        protected, placeholders = protect_placeholders(para)
                        entries.append({
                            'text': restore_placeholders(protected, placeholders),
                            'line_number': idx + 1,
                            'context_line': para,
                            'text_type': 'monologue',
                            'file_path': file_path
                        })
            continue

        # Python bloklarında sadece _() fonksiyonunu parse et
        if state == "PYTHON":
            try:
                from pyparsing import Literal
                if "_" in stripped:
                    paren = Literal("_") + Suppress("(") + quotedString("text") + Suppress(")")
                    res = paren.parseString(stripped)
                    protected, placeholders = protect_placeholders(res.text[1:-1] if res.text.startswith(("\"", "'")) else res.text)
                    entries.append({
                        'text': restore_placeholders(protected, placeholders),
                        'line_number': idx + 1,
                        'context_line': line,
                        'text_type': 'python_translatable',
                        'file_path': file_path
                    })
                    continue
            except ParseException:
                pass

        # Menü bloklarında argümanlı ve koşullu seçenekleri yakala
        if state == "MENU":
            try:
                menu_arg = quotedString("text") + Optional(Group(Suppress("(") + Word(alphanums + " ") + Suppress(")"))) + Optional(Suppress(" if") + restOfLine) + Suppress(":")
                res = menu_arg.parseString(stripped)
                protected, placeholders = protect_placeholders(res.text[1:-1] if res.text.startswith(("\"", "'")) else res.text)
                entries.append({
                    'text': restore_placeholders(protected, placeholders),
                    'line_number': idx + 1,
                    'context_line': line,
                    'text_type': 'menu',
                    'file_path': file_path
                })
                continue
            except ParseException:
                pass

        # Screen blokları: text, label, tooltip, textbutton displayable'ları
        if state == "SCREEN":
            screen_elem_pat = re.compile(r'\b(text|label|tooltip|textbutton)\s+"([^"]+)"')
            for m in screen_elem_pat.finditer(stripped):
                protected, placeholders = protect_placeholders(m.group(2))
                entries.append({
                    'text': restore_placeholders(protected, placeholders),
                    'line_number': idx + 1,
                    'context_line': line,
                    'text_type': m.group(1),
                    'file_path': file_path
                })
            continue

        # Label veya INIT bloklarında diyalog/narration
        if state in ("LABEL", "INIT"):
            dialog_pat = re.compile(r'^(?:(?P<char>[A-Za-z_][\w]*)\s+)?"(?P<text>(?:[^"\\]|\\.)*)"$')
            m = dialog_pat.match(stripped)
            if m:
                protected, placeholders = protect_placeholders(m.group('text'))
                entries.append({
                    'text': restore_placeholders(protected, placeholders),
                    'line_number': idx + 1,
                    'context_line': line,
                    'text_type': 'dialogue' if m.group('char') else 'narration',
                    'character': m.group('char') or '',
                    'file_path': file_path
                })
                continue
    return entries
