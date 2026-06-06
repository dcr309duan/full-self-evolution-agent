import os
import sys
import json
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.goal_generator import GoalGenerator
from core.av_research_engine import AVResearchEngine
from core.evolution_state import EvolutionState


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory structure for testing."""
    temp_dir = tempfile.mkdtemp()
    # Create necessary subdirectories
    reports_dir = os.path.join(temp_dir, 'reports', 'av-research')
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'knowledge'), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, 'core'), exist_ok=True)
    
    # Create a minimal knowledge base file
    knowledge_file = os.path.join(temp_dir, 'knowledge', 'knowledge_base.json')
    with open(knowledge_file, 'w') as f:
        json.dump({
            "AEC": {
                "summary": "Acoustic Echo Cancellation is a signal processing technique.",
                "sections": {
                    "introduction": "AEC removes echo from audio signals.",
                    "technical_details": "Uses adaptive filters like NLMS.",
                    "applications": "Used in VoIP, teleconferencing.",
                    "challenges": "Double-talk detection, convergence speed.",
                    "future_directions": "Deep learning based AEC is emerging."
                },
                "last_updated": "2024-01-01"
            },
            "ANS": {
                "summary": "Active Noise Suppression reduces ambient noise.",
                "sections": {
                    "introduction": "ANS uses destructive interference.",
                    "technical_details": "Uses adaptive filtering.",
                    "applications": "Headphones, automotive.",
                    "challenges": "Latency, power consumption.",
                    "future_directions": "AI-driven noise cancellation."
                },
                "last_updated": "2024-01-15"
            }
        }, f)
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def evolution_state(temp_project_dir):
    """Create a mock evolution state pointing to the temp project directory."""
    state = MagicMock(spec=EvolutionState)
    state.project_dir = temp_project_dir
    state.knowledge_base_path = os.path.join(temp_project_dir, 'knowledge', 'knowledge_base.json')
    state.reports_dir = os.path.join(temp_project_dir, 'reports')
    state.av_research_dir = os.path.join(temp_project_dir, 'reports', 'av-research')
    return state


@pytest.fixture
def goal_generator(evolution_state):
    """Create a GoalGenerator instance with the mock evolution state."""
    return GoalGenerator(evolution_state)


@pytest.fixture
def research_engine(evolution_state):
    """Create an AVResearchEngine instance with the mock evolution state."""
    return AVResearchEngine(evolution_state)


class TestAVResearchIntegration:
    """Integration tests for the AV research pipeline."""

    def test_trigger_aec_research_and_generate_report(self, goal_generator, research_engine, temp_project_dir):
        """Test 1: Trigger an AV_RESEARCH goal for 'AEC' and verify a report is generated."""
        # Trigger the goal for AEC
        goal = goal_generator.generate_goal("AV_RESEARCH", topic="AEC")
        assert goal is not None, "Goal generation failed for AEC"
        assert goal["type"] == "AV_RESEARCH"
        assert goal["topic"] == "AEC"
        
        # Execute the research
        result = research_engine.execute_research(goal)
        assert result is not None, "Research execution returned None"
        assert result["status"] == "completed", f"Research status: {result['status']}"
        
        # Verify report file exists
        report_path = os.path.join(temp_project_dir, 'reports', 'av-research', 'AEC_report.md')
        assert os.path.exists(report_path), f"Report file not found at {report_path}"
        
        # Read and verify report content
        with open(report_path, 'r') as f:
            report_content = f.read()
        
        assert len(report_content) > 0, "Report is empty"
        assert "AEC" in report_content or "Acoustic Echo Cancellation" in report_content, \
            "Report does not contain expected topic content"

    def test_report_contains_required_sections(self, goal_generator, research_engine, temp_project_dir):
        """Test 2: Verify the report contains all required sections."""
        required_sections = [
            "# AV Research Report",
            "## Topic",
            "## Executive Summary",
            "## Technical Analysis",
            "## Applications",
            "## Challenges",
            "## Future Directions",
            "## References"
        ]
        
        # Generate and execute research
        goal = goal_generator.generate_goal("AV_RESEARCH", topic="AEC")
        research_engine.execute_research(goal)
        
        # Read the generated report
        report_path = os.path.join(temp_project_dir, 'reports', 'av-research', 'AEC_report.md')
        with open(report_path, 'r') as f:
            report_content = f.read()
        
        # Check each required section
        for section in required_sections:
            assert section in report_content, f"Required section '{section}' not found in report"

    def test_knowledge_gap_topic_produces_gap_report(self, goal_generator, research_engine, temp_project_dir):
        """Test 3: Test with a topic that has no existing knowledge (should produce a 'knowledge gap' report)."""
        # Use a topic not in the knowledge base
        unknown_topic = "QuantumAudioProcessing"
        
        # Trigger research for unknown topic
        goal = goal_generator.generate_goal("AV_RESEARCH", topic=unknown_topic)
        assert goal is not None, "Goal generation failed for unknown topic"
        
        # Execute research
        result = research_engine.execute_research(goal)
        assert result is not None, "Research execution returned None"
        
        # Should produce a knowledge gap report
        report_path = os.path.join(temp_project_dir, 'reports', 'av-research', f'{unknown_topic}_report.md')
        assert os.path.exists(report_path), f"Knowledge gap report not found at {report_path}"
        
        # Read and verify it's a gap report
        with open(report_path, 'r') as f:
            report_content = f.read()
        
        assert "knowledge gap" in report_content.lower() or "no existing knowledge" in report_content.lower() or \
               "insufficient data" in report_content.lower(), \
               "Report does not indicate a knowledge gap"

    def test_report_format_compliance(self, goal_generator, research_engine, temp_project_dir):
        """Test 4: Test report format compliance."""
        # Generate a research report
        goal = goal_generator.generate_goal("AV_RESEARCH", topic="AEC")
        research_engine.execute_research(goal)
        
        report_path = os.path.join(temp_project_dir, 'reports', 'av-research', 'AEC_report.md')
        with open(report_path, 'r') as f:
            report_content = f.read()
        
        # Check format compliance
        lines = report_content.split('\n')
        
        # First line should be a level-1 heading
        assert lines[0].startswith('# '), "Report must start with a level-1 heading"
        
        # Check for consistent heading structure
        heading_levels = []
        for line in lines:
            if line.startswith('#'):
                level = len(line.split(' ')[0])
                heading_levels.append(level)
        
        # Headings should be properly nested (no skipping levels)
        for i in range(1, len(heading_levels)):
            assert abs(heading_levels[i] - heading_levels[i-1]) <= 1, \
                f"Heading level jump detected: {heading_levels[i-1]} -> {heading_levels[i]}"
        
        # Check for proper Markdown formatting
        assert '**' in report_content or '*' in report_content, "Report should contain formatted text"
        
        # Check for bullet points or numbered lists
        assert any(line.strip().startswith('- ') or line.strip().startswith('* ') or 
                   line.strip()[0].isdigit() for line in lines), \
                   "Report should contain list items"
        
        # Verify report has a reasonable length (at least 100 characters)
        assert len(report_content) >= 100, f"Report too short: {len(report_content)} characters"

    def test_multiple_research_topics(self, goal_generator, research_engine, temp_project_dir):
        """Additional test: Verify multiple research topics can be processed."""
        topics = ["AEC", "ANS", "H264"]
        
        for topic in topics:
            goal = goal_generator.generate_goal("AV_RESEARCH", topic=topic)
            if goal:
                result = research_engine.execute_research(goal)
                assert result is not None, f"Research failed for topic: {topic}"
                
                report_path = os.path.join(temp_project_dir, 'reports', 'av-research', f'{topic}_report.md')
                if result["status"] == "completed":
                    assert os.path.exists(report_path), f"Report not generated for topic: {topic}"
                else:
                    # For topics without knowledge, should still generate a gap report
                    assert os.path.exists(report_path), f"Gap report not generated for topic: {topic}"

    def test_report_metadata(self, goal_generator, research_engine, temp_project_dir):
        """Additional test: Verify report contains metadata."""
        goal = goal_generator.generate_goal("AV_RESEARCH", topic="AEC")
        result = research_engine.execute_research(goal)
        
        # Check result metadata
        assert "timestamp" in result, "Result missing timestamp"
        assert "topic" in result, "Result missing topic"
        assert "status" in result, "Result missing status"
        
        # Verify report file metadata
        report_path = os.path.join(temp_project_dir, 'reports', 'av-research', 'AEC_report.md')
        stat_info = os.stat(report_path)
        assert stat_info.st_size > 0, "Report file is empty"
        assert stat_info.st_mtime > 0, "Report file has invalid modification time"

    def test_knowledge_base_scanning_functionality(self, goal_generator, research_engine, temp_project_dir):
        """Test 5: Verify knowledge base scanning functionality."""
        # Scan the knowledge base for all topics
        knowledge_base_path = os.path.join(temp_project_dir, 'knowledge', 'knowledge_base.json')
        scanned_topics = research_engine.scan_knowledge_base(knowledge_base_path)
        
        # Verify that known topics are found
        assert "AEC" in scanned_topics, "AEC not found in knowledge base scan"
        assert "ANS" in scanned_topics, "ANS not found in knowledge base scan"
        
        # Verify that unknown topics are not found
        assert "H264" not in scanned_topics, "H264 incorrectly found in knowledge base scan"
        
        # Verify the structure of scanned topics
        for topic in scanned_topics:
            assert "summary" in scanned_topics[topic], f"Topic {topic} missing summary"
            assert "sections" in scanned_topics[topic], f"Topic {topic} missing sections"
            assert "last_updated" in scanned_topics[topic], f"Topic {topic} missing last_updated"

    def test_report_file_creation_in_av_research_dir(self, goal_generator, research_engine, temp_project_dir):
        """Test 6: Validate report file creation in reports/av-research/ directory."""
        # Generate reports for multiple topics
        topics = ["AEC", "ANS", "QuantumAudioProcessing"]
        
        for topic in topics:
            goal = goal_generator.generate_goal("AV_RESEARCH", topic=topic)
            if goal:
                research_engine.execute_research(goal)
        
        # Verify that report files are created in the correct directory
        av_research_dir = os.path.join(temp_project_dir, 'reports', 'av-research')
        
        # Check for AEC report
        aec_report_path = os.path.join(av_research_dir, 'AEC_report.md')
        assert os.path.exists(aec_report_path), "AEC report not found in av-research directory"
        
        # Check for ANS report
        ans_report_path = os.path.join(av_research_dir, 'ANS_report.md')
        assert os.path.exists(ans_report_path), "ANS report not found in av-research directory"
        
        # Check for QuantumAudioProcessing report (should be a gap report)
        gap_report_path = os.path.join(av_research_dir, 'QuantumAudioProcessing_report.md')
        assert os.path.exists(gap_report_path), "QuantumAudioProcessing gap report not found in av-research directory"
        
        # Verify no reports are created outside the av-research directory
        reports_dir = os.path.join(temp_project_dir, 'reports')
        for item in os.listdir(reports_dir):
            if item.endswith('.md'):
                assert item.startswith('av-research/'), f"Report {item} created outside av-research directory"

    def test_module_imports_correctly(self):
        """Test that the module imports correctly and produces expected output."""
        # Verify that the core modules can be imported
        from core.goal_generator import GoalGenerator
        from core.av_research_engine import AVResearchEngine
        from core.evolution_state import EvolutionState
        
        # Verify that the imported classes are callable
        assert callable(GoalGenerator), "GoalGenerator is not callable"
        assert callable(AVResearchEngine), "AVResearchEngine is not callable"
        assert callable(EvolutionState), "EvolutionState is not callable"
        
        # Verify that the modules have expected attributes
        assert hasattr(GoalGenerator, 'generate_goal'), "GoalGenerator missing generate_goal method"
        assert hasattr(AVResearchEngine, 'execute_research'), "AVResearchEngine missing execute_research method"
        assert hasattr(AVResearchEngine, 'scan_knowledge_base'), "AVResearchEngine missing scan_knowledge_base method"
        assert hasattr(EvolutionState, 'project_dir'), "EvolutionState missing project_dir attribute"
        assert hasattr(EvolutionState, 'knowledge_base_path'), "EvolutionState missing knowledge_base_path attribute"
        assert hasattr(EvolutionState, 'reports_dir'), "EvolutionState missing reports_dir attribute"
        assert hasattr(EvolutionState, 'av_research_dir'), "EvolutionState missing av_research_dir attribute"
        
        # Verify that the module can produce expected output
        # Create a minimal EvolutionState instance
        temp_dir = tempfile.mkdtemp()
        try:
            # Create necessary directories
            os.makedirs(os.path.join(temp_dir, 'reports', 'av-research'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, 'knowledge'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, 'core'), exist_ok=True)
            
            # Create a minimal knowledge base
            knowledge_file = os.path.join(temp_dir, 'knowledge', 'knowledge_base.json')
            with open(knowledge_file, 'w') as f:
                json.dump({"TestTopic": {"summary": "Test summary", "sections": {}, "last_updated": "2024-01-01"}}, f)
            
            # Create EvolutionState instance
            state = EvolutionState()
            state.project_dir = temp_dir
            state.knowledge_base_path = knowledge_file
            state.reports_dir = os.path.join(temp_dir, 'reports')
            state.av_research_dir = os.path.join(temp_dir, 'reports', 'av-research')
            
            # Create GoalGenerator and AVResearchEngine instances
            goal_gen = GoalGenerator(state)
            research_eng = AVResearchEngine(state)
            
            # Generate a goal and execute research
            goal = goal_gen.generate_goal("AV_RESEARCH", topic="TestTopic")
            assert goal is not None, "Goal generation failed"
            assert goal["type"] == "AV_RESEARCH", f"Unexpected goal type: {goal['type']}"
            assert goal["topic"] == "TestTopic", f"Unexpected topic: {goal['topic']}"
            
            result = research_eng.execute_research(goal)
            assert result is not None, "Research execution failed"
            assert "status" in result, "Result missing status"
            assert "topic" in result, "Result missing topic"
            assert "timestamp" in result, "Result missing timestamp"
            
            # Verify report file was created
            report_path = os.path.join(temp_dir, 'reports', 'av-research', 'TestTopic_report.md')
            assert os.path.exists(report_path), "Report file not created"
            
            # Verify report content
            with open(report_path, 'r') as f:
                report_content = f.read()
            assert len(report_content) > 0, "Report is empty"
            assert "TestTopic" in report_content, "Report missing topic content"
            
        finally:
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    pytest.main([__file__])