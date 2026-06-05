import os

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-661b2c7a20304e82ba8bc5713162247e")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_REASONER = "deepseek-reasoner"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
EVOLUTION_STATE_FILE = os.path.join(MEMORY_DIR, "evolution_state.json")
KNOWLEDGE_BASE_FILE = os.path.join(MEMORY_DIR, "knowledge_base.json")
GOALS_FILE = os.path.join(MEMORY_DIR, "goals.json")

MAX_EVOLUTION_CYCLES = 1000
CYCLE_INTERVAL_SECONDS = 30
