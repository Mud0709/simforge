"""Per-agent cost and final answer from subagent JSONL transcripts."""
import json, sys, os
D = "/tmp/claude-0/-home-user-simforge/173151ff-3d21-569e-8feb-4af905eba41f"
def parse(aid):
    tools = res_bytes = gcalls = 0
    u = dict(inp=0, cw=0, cr=0, out=0)
    answer = ""
    seen = set()
    for line in open(f"{D}/tasks/{aid}.output"):
        d = json.loads(line)
        m = d.get("message") or {}
        c = m.get("content")
        if d.get("type") == "assistant":
            mid = m.get("id")
            us = m.get("usage")
            if us and mid not in seen:  # one API message may span several lines
                seen.add(mid)
                u["inp"] += us.get("input_tokens", 0); u["cw"] += us.get("cache_creation_input_tokens", 0)
                u["cr"] += us.get("cache_read_input_tokens", 0); u["out"] += us.get("output_tokens", 0)
            for b in c if isinstance(c, list) else []:
                if b.get("type") == "tool_use":
                    if b["name"] == "SubagentHandback":
                        answer = json.dumps(b.get("input", {}))
                    else:
                        tools += 1
                        if "graphify" in json.dumps(b.get("input", {})): gcalls += 1
                elif b.get("type") == "text" and b.get("text", "").strip():
                    answer = b["text"]
        elif d.get("type") == "user" and isinstance(c, list):
            for b in c:
                if b.get("type") == "tool_result":
                    rc = b.get("content")
                    s = rc if isinstance(rc, str) else "".join(x.get("text", "") for x in rc or [] if isinstance(x, dict))
                    res_bytes += len(s.encode())
    # cost in "input-token equivalents" at Sonnet ratios: write 1.25x, read 0.1x, output 5x
    cost = u["inp"] + 1.25 * u["cw"] + 0.1 * u["cr"] + 5 * u["out"]
    return tools, gcalls, res_bytes, u, cost, answer
if __name__ == "__main__":
    t, g, b, u, c, a = parse(sys.argv[1]); print(t, g, b, u, round(c)); print(a[:300])
