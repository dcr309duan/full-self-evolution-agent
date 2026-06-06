import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Attempt to import the module without errors
try:
    from core.nash_detector_and_forcer import (
        detect_nash_equilibrium,
        generate_mutations,
        force_nash_equilibrium,
        is_pure_nash,
        compute_best_responses,
        is_strict_nash,
        is_weak_nash,
        get_nash_properties
    )
    IMPORT_SUCCESS = True
except ImportError as e:
    IMPORT_SUCCESS = False
    IMPORT_ERROR = str(e)

# Test data: a simple 2x2 game matrix (payoffs for player 1)
# Row player strategies: [0, 1], Column player strategies: [0, 1]
# Payoff matrix for player 1:
#   (0,0): 3, (0,1): 0
#   (1,0): 0, (1,1): 1
# Best responses: (0,0) is pure Nash (3 >= 0 and 3 >= 0 for player 1, but need both players)
# For simplicity, we test with a symmetric game where (0,0) is Nash

PAYOFF_MATRIX = [
    [3, 0],
    [0, 1]
]

# Another test matrix: Prisoner's Dilemma
# Cooperate (0) vs Defect (1)
# Payoffs: (C,C)=3, (C,D)=0, (D,C)=5, (D,D)=1
PD_MATRIX = [
    [3, 0],
    [5, 1]
]

def test_import():
    """Test that the module can be imported without errors."""
    assert IMPORT_SUCCESS, f"Failed to import nash_detector_and_forcer: {IMPORT_ERROR}"
    print("✓ Import test passed")

def test_detect_nash_equilibrium():
    """Test equilibrium detection with mock data."""
    # Test with a simple 2x2 matrix where (0,0) should be Nash
    # For a symmetric game, we need to check both players
    # We'll use a simple approach: check if detect_nash_equilibrium returns something reasonable
    
    # Test that the function exists and returns a list
    result = detect_nash_equilibrium(PAYOFF_MATRIX)
    assert isinstance(result, list), "detect_nash_equilibrium should return a list"
    
    # Test with PD matrix (should have (1,1) as Nash)
    pd_result = detect_nash_equilibrium(PD_MATRIX)
    assert isinstance(pd_result, list), "detect_nash_equilibrium should return a list for PD"
    
    print("✓ detect_nash_equilibrium test passed")

def test_is_pure_nash():
    """Test pure Nash equilibrium detection."""
    # Test that (0,0) is a pure Nash in the first matrix
    assert is_pure_nash(PAYOFF_MATRIX, 0, 0), "(0,0) should be pure Nash in test matrix"
    
    # Test that (0,0) is not a pure Nash in PD (player 1 can defect for better payoff)
    assert not is_pure_nash(PD_MATRIX, 0, 0), "(0,0) should not be pure Nash in PD"
    
    # Test that (1,1) is a pure Nash in PD
    assert is_pure_nash(PD_MATRIX, 1, 1), "(1,1) should be pure Nash in PD"
    
    print("✓ is_pure_nash test passed")

def test_compute_best_responses():
    """Test best response computation."""
    # For the first matrix, best response to column 0 should be row 0 (payoff 3 > 0)
    br = compute_best_responses(PAYOFF_MATRIX, 0)
    assert 0 in br, "Best response to column 0 should include row 0"
    
    # For PD, best response to column 0 should be row 1 (payoff 5 > 3)
    br_pd = compute_best_responses(PD_MATRIX, 0)
    assert 1 in br_pd, "Best response to column 0 in PD should include row 1"
    
    print("✓ compute_best_responses test passed")

def test_is_strict_nash():
    """Test strict Nash equilibrium detection."""
    # (0,0) in first matrix: 3 > 0 for player 1, and for player 2 it's symmetric
    # Assuming symmetric payoffs for player 2 (same matrix)
    assert is_strict_nash(PAYOFF_MATRIX, 0, 0), "(0,0) should be strict Nash in test matrix"
    
    # (1,1) in PD: 1 > 0 for player 1, and for player 2 it's 1 > 0
    assert is_strict_nash(PD_MATRIX, 1, 1), "(1,1) should be strict Nash in PD"
    
    print("✓ is_strict_nash test passed")

def test_is_weak_nash():
    """Test weak Nash equilibrium detection."""
    # Create a matrix with weak Nash: (0,0) where payoff equals another strategy
    weak_matrix = [
        [3, 0],
        [3, 1]
    ]
    # (0,0): player 1 gets 3, switching to row 1 also gives 3 (weak)
    assert is_weak_nash(weak_matrix, 0, 0), "(0,0) should be weak Nash in test matrix"
    
    # (0,0) in first matrix is strict, not weak
    assert not is_weak_nash(PAYOFF_MATRIX, 0, 0), "(0,0) should not be weak Nash in strict matrix"
    
    print("✓ is_weak_nash test passed")

def test_get_nash_properties():
    """Test getting Nash equilibrium properties."""
    props = get_nash_properties(PAYOFF_MATRIX, 0, 0)
    assert isinstance(props, dict), "get_nash_properties should return a dict"
    assert 'is_nash' in props, "Properties dict should contain 'is_nash'"
    assert 'is_strict' in props, "Properties dict should contain 'is_strict'"
    assert 'is_weak' in props, "Properties dict should contain 'is_weak'"
    
    print("✓ get_nash_properties test passed")

def test_generate_mutations():
    """Test multi-module mutation generation."""
    # Test with a simple matrix
    mutations = generate_mutations(PAYOFF_MATRIX)
    assert isinstance(mutations, list), "generate_mutations should return a list"
    
    # Test that mutations are non-empty for a non-Nash matrix
    # Create a matrix with no pure Nash (Rock-Paper-Scissors style)
    rps_matrix = [
        [0, -1, 1],
        [1, 0, -1],
        [-1, 1, 0]
    ]
    rps_mutations = generate_mutations(rps_matrix)
    assert len(rps_mutations) > 0, "RPS matrix should have mutations"
    
    print("✓ generate_mutations test passed")

def test_force_nash_equilibrium():
    """Test forcing Nash equilibrium."""
    # Test with a matrix that doesn't have a Nash equilibrium
    rps_matrix = [
        [0, -1, 1],
        [1, 0, -1],
        [-1, 1, 0]
    ]
    forced = force_nash_equilibrium(rps_matrix)
    assert isinstance(forced, list), "force_nash_equilibrium should return a list"
    assert len(forced) > 0, "Should produce at least one forced equilibrium"
    
    # Verify the forced matrix has a Nash equilibrium
    for forced_matrix in forced:
        ne = detect_nash_equilibrium(forced_matrix)
        assert len(ne) > 0, "Forced matrix should have at least one Nash equilibrium"
    
    print("✓ force_nash_equilibrium test passed")

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        test_import,
        test_detect_nash_equilibrium,
        test_is_pure_nash,
        test_compute_best_responses,
        test_is_strict_nash,
        test_is_weak_nash,
        test_get_nash_properties,
        test_generate_mutations,
        test_force_nash_equilibrium
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} raised exception: {e}")
            failed += 1
    
    print(f"\n{'='*40}")
    print(f"Tests passed: {passed}/{len(tests)}")
    print(f"Tests failed: {failed}/{len(tests)}")
    
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()