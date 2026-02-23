#!/usr/bin/env python3
import re
import sys

try:
    import yaml
except Exception:
    print("Error: PyYAML is required", file=sys.stderr)
    sys.exit(1)

args = sys.argv[1:]
if args and args[0] == "eval":
    args = args[1:]

# Accept a minimal subset of mikefarah/yq flags used by spaw.sh.
args = [a for a in args if a != "-r"]

if len(args) < 2:
    print("Usage: yq [eval] [-r] <expr> <file>", file=sys.stderr)
    sys.exit(1)

expr = args[0].strip()
path = args[1]

with open(path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)


def walk(obj, base_expr):
    s = base_expr.strip()
    tokens = re.findall(r"\.([A-Za-z0-9_:-]+)|\[(\d+)\]|\[\"([^\"]+)\"\]", s)
    cur = obj
    for key, idx, quoted_key in tokens:
        if key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(key)
        elif quoted_key:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(quoted_key)
        else:
            if not isinstance(cur, list):
                return None
            i = int(idx)
            if i < 0 or i >= len(cur):
                return None
            cur = cur[i]
    return cur


def yq_type(val):
    if val is None:
        return "!!null"
    if isinstance(val, bool):
        return "!!bool"
    if isinstance(val, dict):
        return "!!map"
    if isinstance(val, list):
        return "!!seq"
    if isinstance(val, int):
        return "!!int"
    if isinstance(val, float):
        return "!!float"
    return "!!str"

if "| keys | .[0]" in expr:
    base = expr.split("|")[0].strip()
    val = walk(data, base)
    if isinstance(val, dict) and val:
        print(next(iter(val.keys())))
    else:
        print("null")
elif "| keys | .[]" in expr:
    base = expr.split("|")[0].strip()
    val = walk(data, base)
    if isinstance(val, dict):
        for k in val.keys():
            print(k)
elif "| type" in expr:
    base = expr.split("|")[0].strip()
    val = walk(data, base)
    print(yq_type(val))
elif "| length" in expr:
    base = expr.split("|")[0].strip()
    val = walk(data, base)
    if isinstance(val, (list, dict, str)):
        print(len(val))
    elif val is None:
        print("0")
    else:
        print("1")
else:
    val = walk(data, expr)
    if isinstance(val, bool):
        print("true" if val else "false")
    elif val is None:
        print("null")
    else:
        print(val)
