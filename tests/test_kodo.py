import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from kodo.interp import Interpreter  # noqa: E402
from kodo.errors import KodoError  # noqa: E402


class Cap(object):
    def __init__(self, answers=()):
        self.out, self.answers = [], list(answers)

    def print(self, s):
        self.out.append(s)

    def prompt(self, name, label):
        return self.answers.pop(0)


def run(src, answers=()):
    io = Cap(answers)
    it = Interpreter(io, base_dir=os.path.join(os.path.dirname(__file__), "..", "examples"))
    it.load_source(src)
    return it, io.out


class T(unittest.TestCase):
    def test_vars_ops(self):
        _, o = run('net a = 2\nnet b = a * 3 + 1\nprint b\nprint "x" + 1 + true')
        self.assertEqual(o, ["7", "x1true"])

    def test_if_chain(self):
        src = 'net n = 5\nif (n > 9) {\nprint "a"\n} elseif (n > 3) {\nprint "b"\n} else {\nprint "c"\n}'
        self.assertEqual(run(src)[1], ["b"])

    def test_loops(self):
        src = 'net s = 0\nloop.i 4 {\ns += i\n}\nprint s\nloop.for x.[1,2] {\nprint x\n}\nloop.2 {\nprint "z"\n}'
        self.assertEqual(run(src)[1], ["10", "1", "2", "z", "z"])

    def test_function_recursion(self):
        src = 'void f(n) {\nif (n < 2) {\nreturn 1\n}\nreturn n * f(n - 1)\n}\nprint f(5)'
        self.assertEqual(run(src)[1], ["120"])

    def test_array_dict_in(self):
        src = 'net a = [1,2]\npush(a, 3)\nprint len(a)\nnet d = {"k": 9}\nprint d.k\nprint 2 in a'
        self.assertEqual(run(src)[1], ["3", "9", "true"])

    def test_import_in_file(self):
        src = 'import daftar-akun.txt\nprint "kodo" in daftar-akun.txt\nprint "zzz" == in daftar-akun.txt'
        self.assertEqual(run(src)[1], ["true", "false"])

    def test_screen_state_event(self):
        src = ('state c = 0\nvoid inc() {\nc++\n}\n'
               'void.screen main {\ntext ; t."n={c}"\nbutton ; b."x".onclick.active.inc()\n}')
        it, _ = run(src)
        it.start()
        root = it.render()
        it.fire(root["children"][1]["handlers"]["onclick"])
        self.assertEqual(it.render()["children"][0]["text"], "n=1")

    def test_error_has_line(self):
        with self.assertRaises(KodoError) as c:
            run('net a = 1\nprint zzz')
        self.assertEqual(c.exception.line, 2)

    def test_style(self):
        it, _ = run('void.screen style {\nx ; {\ncolor ; #fffff\nset.size ; 15px\n}\n}')
        self.assertIn("color:#ffffff", it.style.css())
        self.assertIn("font-size:15px", it.style.css())


if __name__ == "__main__":
    unittest.main()
