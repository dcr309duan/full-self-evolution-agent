import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.reflection_parser import ReflectionParser
from src.goal_generator import GoalGenerator

class TestReflectionParser(unittest.TestCase):
    """Unit tests for ReflectionParser covering extraction, malformed input, confidence scoring, and integration."""

    def setUp(self):
        self.parser = ReflectionParser()
        self.goal_gen = GoalGenerator()

        # English sample reflections
        self.valid_en = "I struggled with recursion today, but I feel more confident after practicing. Goal: master recursion. Next: solve 5 more problems."
        self.valid_en2 = "Learned about decorators. Goal: use decorators in a project. Next: read documentation."
        self.malformed_en = "Just some random text without structure."
        self.empty_en = ""

        # Chinese sample reflections
        self.valid_cn = "今天学习了递归，虽然有点难，但练习后更有信心。目标：掌握递归。下一步：再做5道题。"
        self.valid_cn2 = "学习了装饰器。目标：在项目中使用装饰器。下一步：阅读文档。"
        self.malformed_cn = "一些没有结构的随机文本。"
        self.empty_cn = ""

        # Mixed language
        self.mixed = "I learned about closures today. 目标：理解闭包。Next: write a closure example."

    def test_extract_all_fields_english(self):
        """Test extraction of all 4 fields from well-formed English reflections."""
        result = self.parser.extract(self.valid_en)
        self.assertIn('struggle', result.get('struggle', '').lower())
        self.assertIn('confident', result.get('feeling', '').lower())
        self.assertIn('master recursion', result.get('goal', '').lower())
        self.assertIn('solve 5 more problems', result.get('next_steps', '').lower())

    def test_extract_all_fields_chinese(self):
        """Test extraction of all 4 fields from well-formed Chinese reflections."""
        result = self.parser.extract(self.valid_cn)
        self.assertIn('递归', result.get('struggle', ''))
        self.assertIn('信心', result.get('feeling', ''))
        self.assertIn('掌握递归', result.get('goal', ''))
        self.assertIn('再做5道题', result.get('next_steps', ''))

    def test_extract_all_fields_mixed(self):
        """Test extraction from mixed language reflection."""
        result = self.parser.extract(self.mixed)
        self.assertIn('closures', result.get('struggle', '').lower())
        self.assertIn('理解闭包', result.get('goal', ''))
        self.assertIn('write a closure example', result.get('next_steps', '').lower())

    def test_malformed_english(self):
        """Test handling of malformed English text."""
        result = self.parser.extract(self.malformed_en)
        self.assertIsNone(result.get('struggle'))
        self.assertIsNone(result.get('feeling'))
        self.assertIsNone(result.get('goal'))
        self.assertIsNone(result.get('next_steps'))

    def test_malformed_chinese(self):
        """Test handling of malformed Chinese text."""
        result = self.parser.extract(self.malformed_cn)
        self.assertIsNone(result.get('struggle'))
        self.assertIsNone(result.get('feeling'))
        self.assertIsNone(result.get('goal'))
        self.assertIsNone(result.get('next_steps'))

    def test_empty_english(self):
        """Test handling of empty English text."""
        result = self.parser.extract(self.empty_en)
        self.assertIsNone(result.get('struggle'))
        self.assertIsNone(result.get('feeling'))
        self.assertIsNone(result.get('goal'))
        self.assertIsNone(result.get('next_steps'))

    def test_empty_chinese(self):
        """Test handling of empty Chinese text."""
        result = self.parser.extract(self.empty_cn)
        self.assertIsNone(result.get('struggle'))
        self.assertIsNone(result.get('feeling'))
        self.assertIsNone(result.get('goal'))
        self.assertIsNone(result.get('next_steps'))

    def test_confidence_scoring_high(self):
        """Test confidence scoring for well-formed reflections."""
        score = self.parser.confidence_score(self.valid_en)
        self.assertGreaterEqual(score, 0.8)
        score_cn = self.parser.confidence_score(self.valid_cn)
        self.assertGreaterEqual(score_cn, 0.8)

    def test_confidence_scoring_low(self):
        """Test confidence scoring for malformed text."""
        score = self.parser.confidence_score(self.malformed_en)
        self.assertLess(score, 0.5)
        score_cn = self.parser.confidence_score(self.malformed_cn)
        self.assertLess(score_cn, 0.5)

    def test_confidence_scoring_empty(self):
        """Test confidence scoring for empty text."""
        score = self.parser.confidence_score(self.empty_en)
        self.assertEqual(score, 0.0)
        score_cn = self.parser.confidence_score(self.empty_cn)
        self.assertEqual(score_cn, 0.0)

    def test_confidence_scoring_partial(self):
        """Test confidence scoring for partially structured text."""
        partial = "Struggled with loops. Goal: practice loops."
        score = self.parser.confidence_score(partial)
        self.assertGreaterEqual(score, 0.5)
        self.assertLess(score, 0.8)

    def test_integration_with_goal_generator(self):
        """Test integration: parse reflection and generate goals."""
        parsed = self.parser.extract(self.valid_en)
        goals = self.goal_gen.generate(parsed)
        self.assertIsInstance(goals, list)
        self.assertTrue(len(goals) > 0)
        self.assertIn('recursion', goals[0].lower())

    def test_integration_with_goal_generator_chinese(self):
        """Test integration with Chinese reflection."""
        parsed = self.parser.extract(self.valid_cn)
        goals = self.goal_gen.generate(parsed)
        self.assertIsInstance(goals, list)
        self.assertTrue(len(goals) > 0)
        self.assertIn('递归', goals[0])

    def test_integration_with_goal_generator_malformed(self):
        """Test integration with malformed reflection yields empty or default goals."""
        parsed = self.parser.extract(self.malformed_en)
        goals = self.goal_gen.generate(parsed)
        self.assertIsInstance(goals, list)
        # Should return empty or default goals
        self.assertEqual(len(goals), 0)

    def test_integration_with_goal_generator_empty(self):
        """Test integration with empty reflection."""
        parsed = self.parser.extract(self.empty_en)
        goals = self.goal_gen.generate(parsed)
        self.assertIsInstance(goals, list)
        self.assertEqual(len(goals), 0)

    def test_confidence_edge_case_none_text(self):
        """Test confidence scoring with None input."""
        with self.assertRaises(TypeError):
            self.parser.confidence_score(None)

    def test_confidence_edge_case_non_string(self):
        """Test confidence scoring with non-string input."""
        with self.assertRaises(TypeError):
            self.parser.confidence_score(12345)

    def test_extract_edge_case_none_text(self):
        """Test extraction with None input."""
        with self.assertRaises(TypeError):
            self.parser.extract(None)

    def test_extract_edge_case_non_string(self):
        """Test extraction with non-string input."""
        with self.assertRaises(TypeError):
            self.parser.extract(True)

if __name__ == '__main__':
    unittest.main()