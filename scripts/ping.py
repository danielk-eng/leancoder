import sys, json
sys.path.insert(0, ".")
from leancoder.config import Settings
from leancoder.llm import LLM
s = Settings.from_env()
llm = LLM(s)
model = sys.argv[1]
r = llm.chat(model, [{"role": "user", "content": "Reply with exactly: pong"}], max_tokens=int(sys.argv[2]) if len(sys.argv) > 2 else 40, tag="ping")
print(repr(r.text), r.prompt_tokens, r.completion_tokens, r.served_by, r.is_fallback)
