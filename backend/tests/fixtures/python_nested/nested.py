"""Fixture exercising nested functions, nested classes, and dynamic calls (T-04)."""


def outer(x):
    def inner(y):
        return y * 2

    return inner(x) + helper()


def helper():
    return 1


class Wrapper:
    class Inner:
        def run(self):
            return self._step()

        def _step(self):
            label = getattr(self, "label", "none")
            return len(label)

    def make(self):
        return Wrapper.Inner()


def dynamic_caller(obj, method):
    return getattr(obj, method)()
