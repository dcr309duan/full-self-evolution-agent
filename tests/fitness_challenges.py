import unittest

# Challenge 1: FizzBuzz
def fizzbuzz(n):
    """
    Return a list of strings for numbers 1 to n where:
    - Multiples of 3 are replaced with "Fizz"
    - Multiples of 5 are replaced with "Buzz"
    - Multiples of both 3 and 5 are replaced with "FizzBuzz"
    """
    result = []
    for i in range(1, n + 1):
        if i % 3 == 0 and i % 5 == 0:
            result.append("FizzBuzz")
        elif i % 3 == 0:
            result.append("Fizz")
        elif i % 5 == 0:
            result.append("Buzz")
        else:
            result.append(str(i))
    return result

# Challenge 2: Palindrome Check
def is_palindrome(s):
    """
    Return True if the string s is a palindrome (case-insensitive, ignoring non-alphanumeric characters).
    """
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]

# Challenge 3: Factorial
def factorial(n):
    """
    Return the factorial of n (n!). Assume n is a non-negative integer.
    """
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result

# Challenge 4: Reverse String
def reverse_string(s):
    """
    Return the reverse of the input string s.
    """
    return s[::-1]

# Challenge 5: Sum of Digits
def sum_of_digits(n):
    """
    Return the sum of the digits of the integer n. n can be negative.
    """
    n = abs(n)
    total = 0
    while n > 0:
        total += n % 10
        n //= 10
    return total


class TestFitnessChallenges(unittest.TestCase):

    # FizzBuzz Tests
    def test_fizzbuzz_basic(self):
        self.assertEqual(fizzbuzz(15), 
                         ["1","2","Fizz","4","Buzz","Fizz","7","8","Fizz","Buzz","11","Fizz","13","14","FizzBuzz"])

    def test_fizzbuzz_one(self):
        self.assertEqual(fizzbuzz(1), ["1"])

    def test_fizzbuzz_zero(self):
        self.assertEqual(fizzbuzz(0), [])

    # Palindrome Tests
    def test_palindrome_simple(self):
        self.assertTrue(is_palindrome("racecar"))

    def test_palindrome_mixed_case(self):
        self.assertTrue(is_palindrome("A man, a plan, a canal: Panama"))

    def test_palindrome_not(self):
        self.assertFalse(is_palindrome("hello"))

    def test_palindrome_empty(self):
        self.assertTrue(is_palindrome(""))

    # Factorial Tests
    def test_factorial_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_factorial_positive(self):
        self.assertEqual(factorial(5), 120)

    def test_factorial_large(self):
        self.assertEqual(factorial(10), 3628800)

    def test_factorial_negative(self):
        with self.assertRaises(ValueError):
            factorial(-1)

    # Reverse String Tests
    def test_reverse_string_basic(self):
        self.assertEqual(reverse_string("hello"), "olleh")

    def test_reverse_string_empty(self):
        self.assertEqual(reverse_string(""), "")

    def test_reverse_string_palindrome(self):
        self.assertEqual(reverse_string("racecar"), "racecar")

    # Sum of Digits Tests
    def test_sum_of_digits_positive(self):
        self.assertEqual(sum_of_digits(12345), 15)

    def test_sum_of_digits_negative(self):
        self.assertEqual(sum_of_digits(-12345), 15)

    def test_sum_of_digits_zero(self):
        self.assertEqual(sum_of_digits(0), 0)

    def test_sum_of_digits_single(self):
        self.assertEqual(sum_of_digits(7), 7)


if __name__ == '__main__':
    unittest.main()