import unittest
from unittest.mock import MagicMock, patch
from static_predictor import StaticPredictor
from dependency_graph import DependencyGraph
from mutation_proposer import MutationProposer
from schema_contract import SchemaContract
from failure_insight_logger import FailureInsightLogger

class TestStaticPredictor(unittest.TestCase):
    def setUp(self):
        # Set up a small dependency graph with 3 modules
        self.dep_graph = DependencyGraph()
        self.dep_graph.add_module("module_a", dependencies=[])
        self.dep_graph.add_module("module_b", dependencies=["module_a"])
        self.dep_graph.add_module("module_c", dependencies=["module_b"])
        
        # Mock the mutation proposer to return a mutation that breaks a schema contract
        self.mutation_proposer = MagicMock(spec=MutationProposer)
        self.mutation_proposer.propose_mutation.return_value = {
            "module": "module_c",
            "type": "schema_break",
            "details": "Change return type from int to str"
        }
        
        # Mock the schema contract to detect the break
        self.schema_contract = MagicMock(spec=SchemaContract)
        self.schema_contract.check_contract.return_value = False  # Contract broken
        
        # Mock the failure insight logger
        self.failure_logger = MagicMock(spec=FailureInsightLogger)
        
        # Create the predictor with mocked dependencies
        self.predictor = StaticPredictor(
            dep_graph=self.dep_graph,
            mutation_proposer=self.mutation_proposer,
            schema_contract=self.schema_contract,
            failure_logger=self.failure_logger
        )

    def test_mutation_aborts_with_high_score(self):
        # Act
        result = self.predictor.predict()
        
        # Assert that the predictor aborts with score > threshold
        self.assertTrue(result.aborted, "Predictor should abort when schema contract is broken")
        self.assertGreater(result.score, 0.8, "Score should be above threshold for schema-breaking mutation")
        
        # Assert that no actual mutation was executed
        self.mutation_proposer.propose_mutation.assert_called_once()
        # Verify that the mutation was not applied (no execution method called)
        self.mutation_proposer.execute_mutation.assert_not_called()
        
        # Assert that failure insight was logged
        self.failure_logger.log_failure.assert_called_once()
        # Optionally verify the logged insight content
        logged_call = self.failure_logger.log_failure.call_args
        self.assertIn("schema_break", str(logged_call), "Failure insight should mention schema break")

if __name__ == '__main__':
    unittest.main()