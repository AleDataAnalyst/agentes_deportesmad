import py_compile, traceback, os, re

files = ["agentes/llm.py", "agentes/tools/vision.py", "agentes/nodes/vision.py",
         "agentes/agent.py", "agentes/graph.py"]

for f in files:
    s = open(f, encoding="utf-8").read()
    lines = s.splitlines()
    try:
        py_compile.compile(f, doraise=True)
        ok = "COMPILE OK"
    except py_compile.PyCompileError as e:
        ok = "COMPILE ERR"
        err = str(e).strip().replace("\n", " / ")
    print(f"* {f}  [{len(lines)} lines]  {ok}")
    if ok != "COMPILE OK":
        print("    ->", err)
    print("    last:", repr(lines[-1]))

print("\n--- search: 'Error f-string' pattern (table crit #1) ---")
for pat in ["error=f\"Error:", 'error=f"Error']:
    for f in ["agentes/llm.py", "agentes/tools/vision.py", "agentes/nodes/vision.py"]:
        s = open(f, encoding="utf-8").read()
        for i, l in enumerate(s.splitlines(), 1):
            if "Error:" in l:
                print(f'{f}:{i}: {l.strip()}')
