from enum import Enum

class PressureType(Enum):
    NEW_TEST = "new_test"
    TEST_MODIFICATION = "test_modification"
    TEST_DELETION = "test_deletion"
    PARAMETER_SHIFT = "parameter_shift"

    def __str__(self):
        return self.value