import pytest
from src.counter import Counter

@pytest.fixture
def counter():
    return Counter()

class TestCounterV1:
    def test_counter_starts_at_zero(self, counter):
        assert counter.value == 0

    def test_increment_by_one(self, counter):
        counter.increment()
        assert counter.value == 1

    def test_increment_by_positive_number(self, counter):
        counter.increment(5)
        assert counter.value == 5

    def test_multiple_increments(self, counter):
        counter.increment()
        counter.increment(2)
        counter.increment(3)
        assert counter.value == 6

    def test_increment_by_zero(self, counter):
        counter.increment(0)
        assert counter.value == 0

    def test_increment_by_negative_number(self, counter):
        counter.increment(-3)
        assert counter.value == -3

    def test_negative_increment_from_positive(self, counter):
        counter.increment(10)
        counter.increment(-4)
        assert counter.value == 6

    def test_large_negative_increment(self, counter):
        counter.increment(-100)
        assert counter.value == -100

    def test_chain_of_negative_increments(self, counter):
        counter.increment(-1)
        counter.increment(-2)
        counter.increment(-3)
        assert counter.value == -6

    def test_mixed_increments(self, counter):
        counter.increment(5)
        counter.increment(-3)
        counter.increment(2)
        counter.increment(-1)
        assert counter.value == 3