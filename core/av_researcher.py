from core.av_research_engine import ResearchEngine

def run():
    """Run research on all 4 topics sequentially with error handling."""
    engine = ResearchEngine()
    topics = [
        "AI safety alignment",
        "Constitutional AI",
        "Reinforcement learning from human feedback",
        "Self-modifying code safety"
    ]
    for topic in topics:
        try:
            result = engine.research(topic)
            print(f"[AV Researcher] Completed research on: {topic}")
            print(f"  Result: {result[:100]}..." if len(result) > 100 else f"  Result: {result}")
        except Exception as e:
            print(f"[AV Researcher] Error researching '{topic}': {e}")

if __name__ == "__main__":
    run()