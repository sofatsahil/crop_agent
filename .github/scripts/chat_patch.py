import os, sys, subprocess, tempfile, json, base64
from pathlib import Path
import requests

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN")
REPO           = os.environ.get("REPO")
PR_NUMBER      = os.environ.get("PR_NUMBER")

if not (OPENAI_API_KEY and GITHUB_TOKEN and REPO and PR_NUMBER):
    print("Missing one of: OPENAI_API_KEY, GITHUB_TOKEN, REPO, PR_NUMBER")
    sys.exit(0)

API_URL = "https://api.github.com"

def gh(path, method="GET", **kwargs):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.request(method, f"{API_URL}{path}", headers=headers, **kwargs)
    r.raise_for_status()
    return r

def comment(body: str):
    gh(f"/repos/{REPO}/issues/{PR_NUMBER}/comments", method="POST", json={"body": body})

def get_pr():
    return gh(f"/repos/{REPO}/pulls/{PR_NUMBER}").json()

def get_unified_diff(base_sha: str, head_sha: str) -> str:
    return subprocess.check_output(
        ["git", "diff", "--unified", f"{base_sha}..{head_sha}"],
        text=True
    )

def ask_model_for_patch(diff_text: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    system = (
        "You are a careful code refactoring assistant. "
        "Return a unified diff that applies cleanly on top of HEAD. "
        "Only include changed hunks. No prose."
    )
    rules = """
Fix CropManage API endpoint mistakes:
1) List ranches: GET /v2/ranches.json
2) Prefer: GET /v2/ranches/{Ranch_External_GUID}/plantings.json?active=true
   Fallback numeric: GET /v2/plantings/list-by-ranch.json?ranchId={numericId}&active=true
3) Ranch fields from /v2/ranches.json: Name, Id, Ranch_External_GUID (when present)
4) Normalize ranch name comparisons with .strip().lower()
"""

    prompt = f"{rules}\n\nInput diff:\n{diff_text}"
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":prompt},
        ],
    )
    return resp.choices[0].message.content or ""

def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True, check=False)

def apply_patch_and_push(patch_text: str):
    tmp = Path(tempfile.gettempdir()) / "chat_fix.diff"
    tmp.write_text(patch_text, encoding="utf-8")

    # First try a normal apply
    r = run(["git", "apply", "--whitespace=fix", str(tmp)])
    if r.returncode != 0:
        # Try a 3-way merge apply
        r3 = run(["git", "apply", "--3way", "--whitespace=fix", str(tmp)])
        if r3.returncode != 0:
            # Post diagnostics & the patch so you can apply manually
            comment("❌ Patch failed to apply.\n\n**git apply output:**\n```\n"
                    + (r.stderr or r.stdout) + "\n-- 3way --\n"
                    + (r3.stderr or r3.stdout) + "\n```\n\n"
                    + "**Proposed patch (save as patch.diff and run `git apply --3way patch.diff`)**:\n```diff\n"
                    + patch_text[:65000] + "\n```")
            # Dump any .rej files if present
            rej = run(["bash", "-lc", "ls -1 *.rej 2>/dev/null | head -n 10"])
            if rej.returncode == 0 and rej.stdout.strip():
                files = rej.stdout.strip().splitlines()
                text = []
                for f in files:
                    try:
                        txt = Path(f).read_text(errors="ignore")
                        text.append(f"\n--- {f} ---\n{txt}\n")
                    except:
                        pass
                if text:
                    comment("**Reject files (.rej)**:\n```\n" + "".join(text)[:65000] + "\n```")
            sys.exit(0)

    # Commit & push if applied
    run(["git", "config", "user.name", "chat-fix-bot"])
    run(["git", "config", "user.email", "actions@github.com"])
    run(["git", "add", "-A"])
    rc = run(["git", "commit", "-m", "chore: apply chat-fix patch"])
    if rc.returncode != 0:
        comment("ℹ️ Nothing to commit (patch was empty or already applied).")
        sys.exit(0)
    push = run(["git", "push"])
    if push.returncode == 0:
        comment("✅ Patch applied by Chat Fix Bot.")

def main():
    pr = get_pr()
    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]
    diff = get_unified_diff(base_sha, head_sha)
    if not diff.strip():
        comment("ℹ️ No changes to patch (diff is empty).")
        return
    patch = ask_model_for_patch(diff)
    # --- Guard: only proceed if this looks like a valid unified diff
    if not patch or ("diff --git" not in patch or "--- a/" not in patch or "+++ b/" not in patch or "@@" not in patch):
    comment("⚠️ Model did not return a valid unified diff. Skipping apply.\n\n```diff\n" + (patch or "")[:65000] + "\n```")
    sys.exit(0)

    if "diff --git" not in patch:
        comment("⚠️ Model did not return a valid unified diff; nothing applied.\n"
                "You can re-run after pushing a small change or clarifying in a comment.")
        return
    apply_patch_and_push(patch)

if __name__ == "__main__":
    main()
