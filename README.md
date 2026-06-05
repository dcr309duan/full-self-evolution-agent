# Full Self-Evolution Agent

A fully autonomous self-evolving AI agent that can:
- Reflect on its own capabilities and limitations
- Generate goals for self-improvement
- Modify its own source code
- Accumulate knowledge across evolution cycles
- Track its evolution through git history

## Architecture

```
main.py                  - Entry point
config.py                - Configuration
core/
  llm.py                - DeepSeek API interface
  memory.py             - Memory & knowledge persistence
  reflection.py         - Self-reflection & goal generation
  self_modify.py        - Code self-modification engine
  evolution_loop.py     - Main evolution loop
capabilities/           - Dynamically added capabilities
memory/                 - Persistent state & knowledge
logs/                   - Evolution logs
```

## Running

```bash
python3 main.py [max_cycles]
```

## How it works

1. **Reflect**: Agent reflects on current state, capabilities, and progress
2. **Plan**: Generates goals and plans for self-improvement
3. **Execute**: Modifies its own code, creates new capabilities
4. **Learn**: Records successes, failures, and insights
5. **Evolve**: Repeats, advancing through generations
