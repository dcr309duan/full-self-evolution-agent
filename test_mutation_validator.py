import unittest
from mutation_validator import validate_mutation

class TestMutationValidator(unittest.TestCase):

    def test_valid_code_passes_all_checks(self):
        code = "x = 5\ny = x + 2\nprint(y)"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_syntax_error_fails_syntax_check(self):
        code = "x = 5\ny = x + \nprint(y)"
        result = validate_mutation(code)
        self.assertFalse(result['syntax_check'])
        self.assertIsNotNone(result['syntax_error'])

    def test_undefined_variable_fails_type_check(self):
        code = "x = y + 1"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertFalse(result['type_check'])
        self.assertIsNotNone(result['type_error'])

    def test_infinite_loop_fails_sandbox_check(self):
        code = "while True:\n    pass"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertFalse(result['sandbox_check'])
        self.assertIsNotNone(result['sandbox_error'])

    def test_empty_mutation(self):
        code = ""
        result = validate_mutation(code)
        self.assertFalse(result['syntax_check'])
        self.assertIsNotNone(result['syntax_error'])

    def test_non_python_string(self):
        code = "This is not Python code!"
        result = validate_mutation(code)
        self.assertFalse(result['syntax_check'])
        self.assertIsNotNone(result['syntax_error'])

    def test_valid_code_with_function(self):
        code = "def add(a, b):\n    return a + b\nresult = add(3, 4)"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_undefined_function_call(self):
        code = "result = unknown_function(5)"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertFalse(result['type_check'])
        self.assertIsNotNone(result['type_error'])

    def test_loop_with_break_passes_sandbox(self):
        code = "for i in range(10):\n    if i == 5:\n        break"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_recursive_function_without_base_case(self):
        code = "def recurse():\n    recurse()\nrecurse()"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertFalse(result['sandbox_check'])
        self.assertIsNotNone(result['sandbox_error'])

    def test_code_with_import_statement(self):
        code = "import math\nx = math.sqrt(16)"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_code_with_undefined_import(self):
        code = "import nonexistent_module\nx = nonexistent_module.func()"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertFalse(result['type_check'])
        self.assertIsNotNone(result['type_error'])

    def test_code_with_type_error_in_expression(self):
        code = "x = 'string' + 5"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertFalse(result['type_check'])
        self.assertIsNotNone(result['type_error'])

    def test_code_with_list_comprehension(self):
        code = "squares = [x**2 for x in range(10)]"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_code_with_infinite_while_loop_no_break(self):
        code = "while 1:\n    print('hello')"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertFalse(result['sandbox_check'])
        self.assertIsNotNone(result['sandbox_error'])

    def test_code_with_conditional_break(self):
        code = "x = 0\nwhile True:\n    x += 1\n    if x > 10:\n        break"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_code_with_nested_loops(self):
        code = "for i in range(5):\n    for j in range(5):\n        if i == j:\n            break"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

    def test_code_with_while_true_without_break(self):
        code = "while True:\n    pass"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertFalse(result['sandbox_check'])
        self.assertIsNotNone(result['sandbox_error'])

    def test_code_with_recursive_function_with_base_case(self):
        code = "def factorial(n):\n    if n == 0:\n        return 1\n    else:\n        return n * factorial(n-1)\nresult = factorial(5)"
        result = validate_mutation(code)
        self.assertTrue(result['syntax_check'])
        self.assertTrue(result['type_check'])
        self.assertTrue(result['sandbox_check'])

if __name__ == '__main__':
    unittest.main()