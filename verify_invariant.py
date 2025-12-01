import os
import json
import subprocess
import tempfile
from jinja2 import Template
from config import ABSTRACTED_DIR, VERIFIED_DIR, CBMC_UNWIND, CBMC_TIMEOUT

TEMPLATE = '''#include <assert.h>
void {{ func_name }}() {
    {% for p in ptr_vars %}
    int {{ p }}_idx = 0;
    unsigned char arr_{{ p }}[100] = {0};
    {% endfor %}
    // Input assumption (example)
    __CPROVER_assume(arr_h[0] != 0);

    // Simple invariant: all indices >= 0
    #define INVARIANT \\
        {% for p in ptr_vars %}({{ p }}_idx >= 0) && {% endfor %}(1)

    assert(INVARIANT);
    {{ abstracted_code | indent(4) | replace("\\n", "\\n    ") }}
    assert(INVARIANT);
}
'''


def run_cbmc(c_file):
    try:
        result = subprocess.run(
            ["cbmc", "--unwind", str(CBMC_UNWIND), "--bounds-check", c_file],
            capture_output=True, text=True, timeout=CBMC_TIMEOUT
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"


def main():
    os.makedirs(VERIFIED_DIR, exist_ok=True)
    template = Template(TEMPLATE)

    for fname in os.listdir(ABSTRACTED_DIR):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(ABSTRACTED_DIR, fname)) as f:
            data = json.load(f)

        # 生成 C 文件
        c_code = template.render(
            func_name="test_" + data["id"],
            ptr_vars=data["ptr_vars"],
            abstracted_code=data["abstracted_code"],
            idx=list(data["ptr_vars"].values())[0] if data["ptr_vars"] else "0"
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as tmp:
            tmp.write(c_code)
            tmp_path = tmp.name

        is_safe, log = run_cbmc(tmp_path)
        os.unlink(tmp_path)

        out = {
            "id": data["id"],
            "invariant": "/* auto-generated */ " + ("h_idx >= 0" if data["ptr_vars"] else "true"),
            "verified": is_safe,
            "cbmc_log": log[:2000]  # truncate
        }

        with open(os.path.join(VERIFIED_DIR, fname), 'w') as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
