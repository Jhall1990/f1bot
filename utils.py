class Table():
    def __init__(self, columns):
        self.columns = [[i, len(i) + 2] for i in columns]
        self.rows = []

    def add_row(self, *args):
        assert len(args) == len(self.columns)
        self.rows.append([str(i) for i in args])
        self.resize_cols()

    def separator(self):
        sep = ""
        for _, length in self.columns:
            sep += "+"
            sep += "-" * length
        sep += "+"
        return sep

    def resize_cols(self):
        for row, col in zip(self.rows[-1], self.columns):
            if len(row) + 2 > col[1]:
                col[1] = len(row) + 2

    def output(self):
        out = []
        self.output_header(out)
        self.output_rows(out)
        out.append(self.separator())
        return "\n".join(out)

    def output_header(self, out):
        out.append(self.separator())
        header = ""

        for label, width in self.columns:
            header += f"|{label:^{width}}"
        header += "|"
        out.append(header)
        out.append(self.separator())

    def output_rows(self, out):
        for row in self.rows:
            self.output_row(row, out)

    def output_row(self, row, out):
        text = ""
        for idx, val in enumerate(row):
            width = self.columns[idx][1]
            text += f"|{val:^{width}}"
        text += "|"
        out.append(text)
