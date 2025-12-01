# verify_invariant.py
import os
import re
import json
import subprocess
import tempfile
from pathlib import Path
from jinja2 import Template
from tqdm import tqdm


# ----------------------------
# Helper Functions
# ----------------------------

def extract_scalar_vars(loop_body, ptr_vars):
    """
    Extract scalar variables that are assigned in the loop body.
    These are typically used in bit operations or counters.
    """
    assigned_vars = set()
    # Match left-hand side of assignments: a = ..., a += ..., etc.
    for match in re.finditer(r'(\b[a-zA-Z_]\w*\b)\s*([+\-*/%&|^]?=)', loop_body):
        var = match.group(1)
        if var not in ptr_vars:
            assigned_vars.add(var)
    return sorted(assigned_vars)


def extract_undeclared_symbols(loop_body, ptr_vars):
    """
    Extract identifiers that are likely macros or global constants:
    - Not C keywords
    - Not pointer-related (p, p_idx, arr_p)
    - Not already handled as scalars or pointers
    """
    all_ids = set(re.findall(r'\b[a-zA-Z_]\w*\b', loop_body))

    keywords = {
        'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
        'return', 'break', 'continue', 'assert', 'sizeof', 'int', 'char',
        'void', 'unsigned', 'signed', 'short', 'long', 'struct', 'union',
        '__CPROVER_assume', 'true', 'false', 'NULL'
    }

    ptr_idx_names = {f"{p}_idx" for p in ptr_vars}
    arr_names = {f"arr_{p}" for p in ptr_vars}
    excluded = keywords | ptr_vars | ptr_idx_names | arr_names

    undeclared = sorted(all_ids - excluded)
    # Filter out compiler built-ins and very long names (likely false positives)
    filtered = [v for v in undeclared if len(v) <= 30 and not v.startswith('__')]
    return filtered


# ----------------------------
# Jinja2 Template
# ----------------------------

TEMPLATE = '''
#include <assert.h>
void {{ func_name }}() {
    // Declare pointer indices and arrays
    {% for p in ptr_vars %}
    int {{ p }}_idx = 0;
    unsigned char arr_{{ p }}[100] = {0};
    __CPROVER_assume(arr_{{ p }}[0] != 0);
    {% endfor %}

    // Declare scalar variables that are assigned in the loop
    {% for v in assigned_scalars %}
    unsigned int {{ v }} = 0;
    {% endfor %}

    // Declare unknown symbols as symbolic variables (not const!)
    {% for sym in undeclared_symbols %}
    unsigned int {{ sym }};
    __CPROVER_assume({{ sym }} >= 0);
    {% endfor %}

    // Simple auto-generated invariant: all pointer indices >= 0
    #define INVARIANT \\
        {% for p in ptr_vars %}({{ p }}_idx >= 0) && {% endfor %}(1)

    assert(INVARIANT);
    {{ loop_body }}
    assert(INVARIANT);
}
'''


# ----------------------------
# Main Logic
# ----------------------------

def main():
    abstracted_dir = Path("output/abstracted")
    verified_dir = Path("output/verified")
    verified_dir.mkdir(parents=True, exist_ok=True)

    template = Template(TEMPLATE)

    json_files = list(abstracted_dir.glob("*.json"))
    for json_file in tqdm(json_files, desc="Processing files"):
        with open(json_file) as f:
            data = json.load(f)

        loop_id = data["id"]

        if "abstracted_code" not in data or not data["abstracted_code"].strip():
            # Skipped during abstraction
            result = {
                "id": loop_id,
                "invariant": "true",
                "verified": False,
                "cbmc_log": "Skipped: empty or unsupported loop"
            }
            with open(verified_dir / f"{loop_id}.json", "w") as out_f:
                json.dump(result, out_f, indent=2)
            continue

        ptr_vars = list(data.get("ptr_vars", {}).keys())
        loop_body = data["abstracted_code"]

        # Extract variables
        assigned_scalars = extract_scalar_vars(loop_body, set(ptr_vars))
        undeclared_symbols = extract_undeclared_symbols(loop_body, set(ptr_vars))

        # Generate function name
        func_name = f"test__{loop_id.replace('.', '_').replace('-', '_')}"

        # Render C code
        rendered = template.render(
            func_name=func_name,
            ptr_vars=ptr_vars,
            assigned_scalars=assigned_scalars,
            undeclared_symbols=undeclared_symbols,
            loop_body=loop_body.strip()
        )

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp:
            tmp.write(rendered)
            tmp_path = tmp.name

        try:
            # Run CBMC on the specific function
            result = subprocess.run(
                ['cbmc', '--function', func_name, '--unwind', '20', '--no-library', tmp_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            cbmc_log = result.stdout + result.stderr

            verified = "VERIFICATION SUCCESSFUL" in cbmc_log

        except subprocess.TimeoutExpired:
            cbmc_log = "CBMC timeout"
            verified = False
        except Exception as e:
            cbmc_log = f"Subprocess error: {e}"
            verified = False
        finally:
            os.unlink(tmp_path)

        # Build invariant string
        if ptr_vars:
            inv_parts = [f"{p}_idx >= 0" for p in ptr_vars]
            invariant = "/* auto-generated */ " + " && ".join(inv_parts)
        else:
            invariant = "/* auto-generated */ true"

        # Save result
        result_json = {
            "id": loop_id,
            "invariant": invariant,
            "verified": verified,
            "cbmc_log": cbmc_log
        }

        with open(verified_dir / f"{loop_id}.json", "w") as out_f:
            json.dump(result_json, out_f, indent=2)

    print("Verification completed.")


if __name__ == "__main__":
    main()
