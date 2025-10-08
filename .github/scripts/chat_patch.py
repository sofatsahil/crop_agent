import os
import sys
import re
import json
import tempfile
import subprocess
from pathlib import Path

import requests

# ---------------------- ENV ----------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN")
REPO           = os.environ.get("REPO")            # e.g. "owner/repo"
PR_NUMBER      = os.environ.get("PR_NUMBER")       # set by workflow env
EVENT_NAME     = os.environ.get("EVENT_NAME")      # optional, for logs
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

API_URL = "https://api.github.com"

# ---------------------- Helpers ----------------------
def log(msg: str):
    print(msg, flush=True)

def gh(path, method="GET", **kwargs):
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.request(method, f"{API_URL}{path}", headers=headers, **kwargs)
    r.raise_for_status()
    return r

def comment(body: str):
    """Post a PR comment if PR_NUMBER is known; else print to logs."""
    if not (GITHUB_TOKEN and REPO and PR_NUMBER):
        log("No PR context available for comment; printing instead:\n" + body)
        return
    gh(f"/repos/{REPO}/issues/{PR_NUMBER}/comments",
       method="POST", json={"body": body})

def get_pr():
    if not (REPO and PR_NUMBER):
        log("❗ No REPO/PR_NUMBER found in env; nothing to do.")
        sys.exit(0)
    return gh(f"/repos/{REPO}/pulls/{PR_NUMBER}").json()

def run(cmd):
    """Run a shell command and return CompletedProcess (no exceptions)."""
    log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, text=True, capture_output=True, check=False)

def get_unified_diff(base_sha: str, head_sha: str) -> str:
    """Produce a unified diff of base..head from the local checkout (Actions has already checked out)."""
    cp = run(["git", "diff", "--unified", f"{base_sha}..{head_sha}"])
    if cp.returncode != 0:
        log(cp.stderr or cp.stdout)
    return cp.stdout

# ---------------------- OpenAI ----------------------
def ask_model_for_patch(diff_text: str) -> str:
    """
    Asks the OpenAI model for a **unified diff** (only) to apply on top of HEAD.
    Includes strict rules to avoid whitespace-only changes and to return valid diff format.
    """
    # Lazy import so CI only fails here if needed
    try:
        from openai import OpenAI
    except Exception as e:
        comment(f"❌ Could not import OpenAI SDK: {e}")
        sys.exit(0)

    client = OpenAI(api_key=OPENAI_API_KEY)

    system = (
        "You are a careful code refactoring assistant. "
        "Given a git unified diff (base..head), return a new unified diff that applies cleanly on top of HEAD. "
        "Only include changed hunks. No prose."
    )

    rules = """
Fix CropManage API endpoint mistakes using these rules:
1) List ranches: GET /v2/ranches.json
2) List plantings for a ranch (prefer): GET /v2/ranches/{Ranch_External_GUID}/plantings.json?active=true
   Fallback numeric: GET /v2/plantings/list-by-ranch.json?ranchId={numericId}&active=true
3) Ranch objects from /v2/ranches.json contain Name, Id, and may include Ranch_External_GUID.
4) Normalize ranch name comparisons with .strip().lower().
5) Do NOT produce whitespace-only diffs.
6) Return a valid unified diff ONLY; no explanations or extra text.
"""

    user_prompt = f"{rules}\n\nInput diff (base..head):\n{diff_text}"

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )
        out = resp.choices[0].message.content or ""
        return out
    except Exception as e:
        comment(f"❌ OpenAI request failed: {e}")
        sys.exit(0)

# ---------------------- Patch Application ----------------------
def ensure_valid_unified_diff(patch: str) -> bool:
    """
    Minimal sanity check for a unified diff:
    must contain diff headers and at least one hunk.
    """
    if not patch:
        return False
    tokens = ("diff --git", "--- a/", "+++ b/", "@@")
    return all(t in patch for t in tokens)

def sanitize_patch_whitespace(patch: str) -> str:
    """
    Remove trailing whitespace at end of lines to reduce noisy diffs.
    """
    return re.sub(r"[ \t]+(\r?\n)", r"\1", patch)

def dump_rejects_as_comment():
    """If git created .rej files, post their contents as a comment (first few)."""
    ls = run(["bash", "-lc", "ls -1 **/*.rej 2>/dev/null | head -n 10"])
    if ls.returncode == 0 and ls.stdout.strip():
        files = ls.stdout.strip().splitlines()
        chunks = []
        for f in files:
            try:
                txt = Path(f).read_text(errors="ignore")
                chunks.append(f"\n--- {f} ---\n{txt}\n")
            except Exception:
                pass
        if chunks:
            joined = "".join(chunks)
            comment("**Reject files (.rej)**:\n```\n" + joined[:65000] + "\n```")

def apply_patch_and_push(patch_text: str):
    tmp = Path(tempfile.gettempdir()) / "chat_fix.diff"
    tmp.write_text(patch_text, encoding="utf-8")

    # 1) Try normal apply
    r1 = run(["git", "apply", "--whitespace=fix", str(tmp)])
    if r1.returncode != 0:
        log("Normal apply failed; trying 3-way merge...")
        # 2) Try 3-way apply
        r2 = run(["git", "apply", "--3way", "--whitespace=fix", str(tmp)])
        if r2.returncode != 0:
            # Post diagnostics & the patch so user can apply manually
            comment("❌ Patch failed to apply.\n\n"
                    "**git apply output:**\n```\n"
                    + (r1.stderr or r1.stdout)
                    + "\n-- 3way --\n"
                    + (r2.stderr or r2.stdout)
                    + "\n```\n\n"
                    + "**Proposed patch (save as patch.diff and run `git apply --3way patch.diff`)**:\n```diff\n"
                    + patch_text[:65000]
                    + "\n```")
            dump_rejects_as_comment()
            return

    # 3) Commit & push if applied
    run(["git", "config", "user.name", "chat-fix-bot"])
    run(["git", "config", "user.email", "actions@github.com"])
    run(["git", "add", "-A"])
    c = run(["git", "commit", "-m", "chore: apply chat-fix patch"])
    if c.returncode != 0:
        comment("ℹ️ Nothing to commit (patch was empty or already applied).")
        return
    p = run(["git", "push"])
    if p.returncode == 0:
        comment("✅ Patch applied by Chat Fix Bot.")

# ---------------------- Main ----------------------
def main():
    if not (OPENAI_API_KEY and GITHUB_TOKEN and REPO):
        log("Missing one of: OPENAI_API_KEY, GITHUB_TOKEN, REPO. Exiting.")
        sys.exit(0)

    pr = get_pr()  # exits if missing PR_NUMBER
    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]
    log(f"PR #{PR_NUMBER}: {REPO} base={base_sha[:7]} head={head_sha[:7]} (event={EVENT_NAME})")

    diff = get_unified_diff(base_sha, head_sha)
    if not diff.strip():
        comment("ℹ️ No changes to patch (diff is empty).")
        return

    patch = ask_model_for_patch(diff)

    # --- Guard: only proceed if this looks like a valid unified diff
    if not ensure_valid_unified_diff(patch):
        comment("⚠️ Model did not return a valid unified diff. Skipping apply.\n\n```diff\n"
                + (patch or "")[:65000] + "\n```")
        return

    # Optional hygiene: strip trailing whitespace in the patch
    patch = sanitize_patch_whitespace(patch)

    apply_patch_and_push(patch)

if __name__ == "__main__":
    main()
