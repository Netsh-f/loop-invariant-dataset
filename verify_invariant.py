# verify_invariant.py
import os
import json
import re
import subprocess
import tempfile
from jinja2 import Template
from config import ABSTRACTED_DIR, VERIFIED_DIR

TEMPLATE = '''
#include <assert.h>
void {{ func_name }}() {
    // Declare pointer indices and arrays
    {% for p in ptr_vars %}
    int {{ p }}_idx = 0;
    unsigned char arr_{{ p }}[100] = {0};
    {% endfor %}

    // Declare scalar variables used in loop body
    {% for v in scalar_vars %}
    unsigned int {{ v }} = 0;
    {% endfor %}

    // Input assumption (example)
    __CPROVER_assume(arr_h[0] != 0);

    // Simple invariant: all indices >= 0
    #define INVARIANT \\
        {% for p in ptr_vars %}({{ p }}_idx >= 0) && {% endfor %}(1)

    assert(INVARIANT);
    {{ loop_body }}
    assert(INVARIANT);
}
'''


def extract_scalar_vars(loop_body, ptr_vars):
    """从循环体中提取非指针标量变量"""
    all_ids = set(re.findall(r'\b[a-zA-Z_]\w*\b', loop_body))
    keywords = {
        'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'default',
        'return', 'break', 'continue', 'assert', 'sizeof', 'int', 'char',
        'void', 'unsigned', 'signed', 'short', 'long', 'struct', 'union',
        '__CPROVER_assume'
    }
    ptr_idx_names = {f"{p}_idx" for p in ptr_vars}
    arr_names = {f"arr_{p}" for p in ptr_vars}
    scalar_vars = (
            all_ids
            - ptr_vars
            - ptr_idx_names
            - arr_names
            - keywords
    )
    # 过滤掉纯大写（可能是宏）
    scalar_vars = {v for v in scalar_vars if not v.isupper()}
    return sorted(scalar_vars)


def main():
    os.makedirs(VERIFIED_DIR, exist_ok=True)
    template = Template(TEMPLATE)

    for fname in os.listdir(ABSTRACTED_DIR):
        if not fname.endswith('.json'):
            continue

        with open(os.path.join(ABSTRACTED_DIR, fname)) as f:
            data = json.load(f)

        loop_id = data["id"]
        loop_body = data["abstracted_code"]
        ptr_vars = list(data["ptr_vars"].keys())

        if not loop_body.strip():
            verified = False
            log = "Skipped: empty or unsupported loop"
        else:
            try:
                scalar_vars = extract_scalar_vars(loop_body, set(ptr_vars))
                func_name = f"test_{loop_id.replace('.', '_').replace('-', '_')}"

                rendered = template.render(
                    func_name=func_name,
                    ptr_vars=ptr_vars,
                    scalar_vars=scalar_vars,
                    loop_body=loop_body.strip()
                )

                with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp:
                    tmp.write(rendered)
                    tmp_path = tmp.name

                # Run CBMC
                result = subprocess.run(
                    ['cbmc', '--unwind', '20', tmp_path],
                    capture_output=True,
                    text=True
                )
                os.unlink(tmp_path)

                verified = "VERIFICATION SUCCESSFUL" in result.stdout
                log = result.stdout + result.stderr

            except Exception as e:
                verified = False
                log = str(e)

        out = {
            "id": loop_id,
            "invariant": "/* auto-generated */ " + " && ".join(
                [f"{p}_idx >= 0" for p in ptr_vars]) if ptr_vars else "true",
            "verified": verified,
            "cbmc_log": log[:2000]  # 避免日志过长
        }

        with open(os.path.join(VERIFIED_DIR, fname), 'w') as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
