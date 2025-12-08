import json
import os

from openai import OpenAI

SYSTEM_PROMPT = f"""
You are an expert in formal verification of C code using CBMC.
Your task is to generate a complete, self-contained C program that can be directly passed to CBMC,
including a **meaningful loop invariant** that captures the semantic relationship between output variables and the input array.

### Rules:
1. DO NOT output only bounds checks like `i < N`. The invariant must express program logic.
2. For tag-value scanning loops (e.g., `for(i=0; arr[i]; i+=2) if(arr[i]==TAG) x=arr[i+1];`), 
   the invariant should state:
   - Either no matching tag has been found yet (`x == 0` or initial value), OR
   - A matching tag was found at some earlier even index, and `x` equals the corresponding value.
3. Since CBMC does not support quantifiers (∀/∃), approximate the invariant using the most recent possible match (e.g., `i-2`).
4. If the loop body is a simple array write/update (e.g., a[i] = ..., a[i] += ...), then the loop invariant may focus on memory safety (index bounds). Do NOT use nested loops in __CPROVER_assert. Only for search/scanning loops (e.g., if (a[i]==TAG) x=a[i+1]) should you express semantic relationships.
4. Output ONLY valid C code. No explanations, no markdown.

### Example (few-shot):
Input abstract loop:
  for (i=0; arr_rel[i]; i++) if (arr_rel[i]==R_TLS) base = arr_rel[i+1];

Correct CBMC output:
#include <stddef.h>
#define N 100
#define R_TLS 6

int main() {{
    size_t arr_rel[N];
    size_t base = 0;
    size_t i = 0;

    __CPROVER_assume(N > 1);
    for (size_t k = 0; k < N; k++) {{
        __CPROVER_assume(arr_rel[k] == 0 || arr_rel[k] == R_TLS);
    }}

    while (i < N && arr_rel[i] != 0) {{
        // --- LOOP INVARIANT: base is either unset or matches the last seen R_TLS value ---
        __CPROVER_assert(
            (base == 0) ||
            (i >= 1 && arr_rel[i - 1] == R_TLS && base == arr_rel[i]),
            "Loop invariant violated"
        );

        if (arr_rel[i] == R_TLS) {{
            __CPROVER_assume(i + 1 < N);
            base = arr_rel[i + 1];
        }}
        i++;
    }}
    return 0;
}}
"""


def get_prompt(abstract_code, ptr_map, item):
    return f"""
### Now process this loop:

Abstracted loop:
```
{abstract_code}
```

Pointer mapping (for reference): {ptr_map}
File context: {item}

Generate the CBMC-ready C program with a proper loop invariant.
"""


def main():
    client = OpenAI(api_key=os.environ.get('DEEPSEEK_API_KEY'),
                    base_url="https://api.deepseek.com")
    with open("output/loop_dataset.json", "r", encoding="utf-8") as f:
        loop_dataset = json.load(f)
    for idx, item in enumerate(loop_dataset):
        abstract = item["abstract_code"]
        ptr_map = item["ptr_map"]
        prompt = get_prompt(abstract, ptr_map, item)
        print(f"[{idx + 1}/{len(loop_dataset)}] Sending request...")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        invariant_code = response.choices[0].message.content.strip()
        item["invariant"] = invariant_code
    with open("output/loop_invariant_dataset.json", "w", encoding="utf-8") as f:
        json.dump(loop_dataset, f, indent=2, ensure_ascii=False)
    print("Saved")


if __name__ == "__main__":
    main()
