"""Utility module for parsing test runner output and extracting structured failure information.

This module provides functions to parse pytest-style output, extract test names,
error types, and module paths, and normalize module names for consistent consumption
by FailurePatternDetector.
"""

import re
import ast
from typing import Dict, List, Optional, Tuple


# Regex patterns for parsing pytest output
FAILURE_HEADER_PATTERN = re.compile(
    r'FAILED\s+(?P<test_path>[^\s]+)'
)

TEST_PATH_PATTERN = re.compile(
    r'(?P<module_path>[\w/.]+)::(?P<test_name>[\w_]+)'
)

ERROR_TYPE_PATTERN = re.compile(
    r'(?P<error_type>\w+(?:Error|Exception|Warning|Failure))'
)

MODULE_SEPARATOR_PATTERN = re.compile(r'[\\/]')


def parse_failure_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single line of pytest output for failure information.

    Args:
        line: A line from pytest output.

    Returns:
        A dictionary with keys 'test_name', 'error_type', 'module_path', and 'raw_line',
        or None if the line does not contain a failure.
    """
    match = FAILURE_HEADER_PATTERN.search(line)
    if not match:
        return None

    test_path = match.group('test_path')
    path_match = TEST_PATH_PATTERN.search(test_path)
    if not path_match:
        return None

    module_path = path_match.group('module_path')
    test_name = path_match.group('test_name')

    # Normalize module path (replace OS separators with dots)
    normalized_module = normalize_module_path(module_path)

    # Try to extract error type from the same line or nearby context
    error_type = extract_error_type(line)

    return {
        'test_name': test_name,
        'error_type': error_type,
        'module_path': normalized_module,
        'raw_line': line.strip(),
    }


def extract_error_type(line: str) -> str:
    """Extract error type from a line of pytest output.

    Args:
        line: A line of text potentially containing an error type.

    Returns:
        The extracted error type string, or 'UnknownError' if not found.
    """
    match = ERROR_TYPE_PATTERN.search(line)
    if match:
        return match.group('error_type')
    return 'UnknownError'


def normalize_module_path(module_path: str) -> str:
    """Normalize a module path to a consistent dotted format.

    Converts file paths (with slashes or backslashes) to dotted module notation,
    removes file extensions, and handles relative paths.

    Args:
        module_path: A module path string (e.g., 'tests/test_foo.py' or 'tests\\test_foo').

    Returns:
        A normalized dotted module path (e.g., 'tests.test_foo').
    """
    # Remove file extension if present
    if module_path.endswith('.py'):
        module_path = module_path[:-3]

    # Replace OS-specific separators with dots
    normalized = MODULE_SEPARATOR_PATTERN.sub('.', module_path)

    # Remove leading dots (from relative paths like './module')
    normalized = normalized.lstrip('.')

    # Remove trailing dots
    normalized = normalized.rstrip('.')

    return normalized


def parse_pytest_output(output: str) -> List[Dict[str, str]]:
    """Parse full pytest output and extract all failure information.

    Args:
        output: The complete output from a pytest run (stdout + stderr).

    Returns:
        A list of dictionaries, each containing 'test_name', 'error_type',
        'module_path', and 'raw_line' for each failed test.
    """
    failures = []
    lines = output.split('\n')

    for i, line in enumerate(lines):
        failure_info = parse_failure_line(line)
        if failure_info:
            # Try to get more context from the next line if error type is unknown
            if failure_info['error_type'] == 'UnknownError' and i + 1 < len(lines):
                next_line = lines[i + 1]
                error_type = extract_error_type(next_line)
                if error_type != 'UnknownError':
                    failure_info['error_type'] = error_type
            failures.append(failure_info)

    return failures


def parse_traceback(traceback_text: str) -> List[Dict[str, str]]:
    """Parse a Python traceback string and extract structured frame information.

    Args:
        traceback_text: A Python traceback string.

    Returns:
        A list of dictionaries with keys 'file', 'line', 'function', and 'code'.
    """
    frames = []
    # Pattern for traceback frames
    frame_pattern = re.compile(
        r'File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+),\s+in\s+(?P<function>\w+)'
    )
    code_pattern = re.compile(r'^\s+(?P<code>.+)$')

    lines = traceback_text.split('\n')
    current_frame = None

    for line in lines:
        frame_match = frame_pattern.search(line)
        if frame_match:
            if current_frame:
                frames.append(current_frame)
            current_frame = {
                'file': frame_match.group('file'),
                'line': int(frame_match.group('line')),
                'function': frame_match.group('function'),
                'code': '',
            }
        elif current_frame:
            code_match = code_pattern.match(line)
            if code_match:
                current_frame['code'] = code_match.group('code').strip()

    if current_frame:
        frames.append(current_frame)

    return frames


def extract_failure_details(failure_info: Dict[str, str], traceback: str) -> Dict[str, object]:
    """Combine parsed failure info with traceback details for comprehensive analysis.

    Args:
        failure_info: A dictionary from parse_failure_line or parse_pytest_output.
        traceback: The full traceback string associated with this failure.

    Returns:
        A dictionary with all failure details including parsed traceback frames.
    """
    frames = parse_traceback(traceback)
    return {
        **failure_info,
        'traceback_frames': frames,
        'traceback_raw': traceback,
    }


def format_failure_for_detector(failure: Dict[str, object]) -> Dict[str, object]:
    """Format a failure dictionary for consumption by FailurePatternDetector.

    Ensures consistent keys and types that the detector expects.

    Args:
        failure: A failure dictionary (from parse_failure_line or extract_failure_details).

    Returns:
        A formatted dictionary with keys: 'test_name', 'error_type', 'module_path',
        'traceback_frames' (list), and 'raw_line'.
    """
    return {
        'test_name': failure.get('test_name', ''),
        'error_type': failure.get('error_type', 'UnknownError'),
        'module_path': failure.get('module_path', ''),
        'traceback_frames': failure.get('traceback_frames', []),
        'raw_line': failure.get('raw_line', ''),
    }


# Convenience function for quick parsing
def quick_parse(output: str) -> List[Dict[str, object]]:
    """Quickly parse pytest output and return formatted failures for detector.

    Args:
        output: The complete pytest output.

    Returns:
        A list of formatted failure dictionaries ready for FailurePatternDetector.
    """
    failures = parse_pytest_output(output)
    return [format_failure_for_detector(f) for f in failures]