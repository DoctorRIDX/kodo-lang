class KodoError(Exception):
    def __init__(self, msg, line=None, file=None):
        Exception.__init__(self, msg)
        self.msg = msg
        self.line = line
        self.file = file

    def __str__(self):
        loc = ""
        if self.line is not None:
            loc = " [baris %s%s]" % (self.line, (" di %s" % self.file) if self.file else "")
        return "KodoError: %s%s" % (self.msg, loc)


class ReturnSignal(Exception):
    def __init__(self, value=None):
        Exception.__init__(self)
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class QuitSignal(Exception):
    pass


class NeedInput(Exception):
    """Dilempar mode web saat program meminta input dari user."""
    def __init__(self, name, label):
        Exception.__init__(self, name)
        self.name = name
        self.label = label
