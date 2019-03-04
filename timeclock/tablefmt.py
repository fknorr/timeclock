import sys
from enum import IntEnum


ASCII_STYLE = {
    'corner-top-left': '.',
    'corner-top-right': '.',
    'corner-bottom-left': "'",
    'corner-bottom-right': "'",
    'join-mid': '+',
    'join-top': '-',
    'join-bottom': '-',
    'join-left': '|',
    'join-right': '|',
    'inner-horizontal': '-',
    'inner-vertical': '|',
    'outer-horizontal': '-',
    'outer-vertical': '|',
    'working-state': '>>',
    'paused-state': '::',
    'placeholder': '-?-',
}


BOX_STYLE = {
    'corner-top-left': '\u250c',
    'corner-top-right': '\u2510',
    'corner-bottom-left': '\u2514',
    'corner-bottom-right': '\u2518',
    'join-mid': '\u253c',
    'join-top': '\u252c',
    'join-bottom': '\u2534',
    'join-left': '\u251c',
    'join-right': '\u2524',
    'inner-horizontal': '\u2500',
    'inner-vertical': '\u2502',
    'outer-horizontal': '\u2500',
    'outer-vertical': '\u2502',
    'working-state': '\u25b6',
    'paused-state': '\u23f8',
    'placeholder': '?',
}


class Align(IntEnum):
    LEFT = 0
    CENTER = 1
    RIGHT = 2


class Constraint:
    def __init__(self, min_width: int = 0, max_width: int or None = None):
        self.min_width = min_width
        self.max_width = max_width

    def copy(self):
        return Constraint(self.min_width, self.max_width)

    def include(self, other: 'Constraint'):
        self.min_width = max(self.min_width, other.min_width)
        if self.max_width is not None and other.max_width is not None:
            self.max_width = min(self.max_width, other.max_width)
        elif other.max_width is not None:
            self.max_width = other.max_width


class Column:
    def __init__(self, align: Align = Align.LEFT, constraint: Constraint = Constraint()):
        self.align = align
        self.constraint = constraint

    def pad(self, s: str):
        if self.constraint.max_width is not None and len(s) > self.constraint.max_width:
            if self.constraint.max_width > 3:
                return s[:self.constraint.max_width - 3] + '...'
            else:
                return '.' * self.constraint.max_width

        padding = self.constraint.min_width - len(s)
        if padding > 0:
            if self.align == Align.LEFT:
                return s + ' ' * padding
            elif self.align == Align.CENTER:
                left_pad = padding // 2
                right_pad = padding - left_pad
                return ' ' * left_pad + s + ' ' * right_pad
            elif self.align == Align.RIGHT:
                return ' ' * padding + s
        return s


Column.LEFT = Column(Align.LEFT)
Column.CENTER = Column(Align.CENTER)
Column.RIGHT = Column(Align.RIGHT)


class Row:
    def print(self, columns: [Column], style: dict, file):
        raise NotImplementedError()

    def constraints(self):
        raise NotImplementedError()


class DataRow(Row):
    def __init__(self, cells: list):
        self.cells = [str(v) for v in cells]

    def print(self, columns: [Column], style: dict, file):
        inner = style['inner-vertical']
        outer = style['outer-vertical']
        print(outer, (' ' + inner + ' ').join(c.pad(s) for s, c in zip(self.cells, columns)), outer, file=file)

    def constraints(self):
        return [Constraint(len(s)) for s in self.cells]


def _make_rule(columns: [Column], left: str, dash: str, inner: str, right: str):
    return dash.join([left, (dash + inner + dash).join(c.constraint.min_width * dash for c in columns), right])


class RuleRow(Row):
    def print(self, columns: [Column], style: dict, file):
        print(_make_rule(columns, style['join-left'], style['inner-horizontal'], style['join-mid'],
                         style['join-right']), file=file)

    def constraints(self):
        return []


class Table:
    def __init__(self, columns: [Column]):
        self.columns = columns
        self.rows = []

    def row(self, cells: list):
        self.rows.append(DataRow(cells))

    def rule(self):
        self.rows.append(RuleRow())

    def print(self, style: dict, file=sys.stdout):
        constraints = [c.constraint.copy() for c in self.columns]
        for row in self.rows:
            for a, c in zip(constraints, row.constraints()):
                a.include(c)
        final_columns = [Column(c.align, x) for c, x in zip(self.columns, constraints)]

        print(_make_rule(final_columns, style['corner-top-left'], style['outer-horizontal'], style['join-top'],
                         style['corner-top-right']), file=file)
        for row in self.rows:
            row.print(final_columns, style, file)
        print(_make_rule(final_columns, style['corner-bottom-left'], style['outer-horizontal'], style['join-bottom'],
                         style['corner-bottom-right']), file=file)

