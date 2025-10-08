import os
import sys
import re
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple

import requests

# ---------------------- ENV ----------------------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN")
REPO           = os.environ.get("REPO")            # "owner/repo"
PR_NUMBER      = os.environ.get("PR_NUMBER")       # set by workflow
EVENT_NAME     = os.environ.get("EVENT_NAME", "")
COMMENT_BODY   = os.environ.get("COMMENT_BODY", "")
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
    if not (GITHUB_TOKEN and REPO and PR_NUMBER):
        log("No PR context to comment; printing instead:\n" + body)
        return
    gh(f"/repos/{REPO}/issues/{PR_NUMBER}/comments", method="POST", json={"body": body})

def get_pr():
    if not (REPO and PR_NUMBER):
        log("❗ No REPO/PR_NUMBER; exiting.")
        sys.exit(0)
    return gh(f"/repos/{REPO}/pulls/{PR_NUMBER}").json()

def get_issue_comments() -> List[dict]:
    # PR comments live under /issues/:number/comments
    r = gh(f"/repos/{REPO}/issues/{PR_NUMBER}/comments")
    return r.json()

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, text=True, capture_output=True, check=False)

def get_unified_diff(base_sha: str, head_sha: str) -> str:
    cp = run(["git", "diff", "--unified", f"{base_sha}..{head_sha}"])
    if cp.returncode != 0:
        log(cp.stderr or cp.stdout)
    return cp.stdout

def get_changed_files(base_sha: str, head_sha: str) -> List[str]:
    cp = run(["git", "diff", "--name-only", f"{base_sha}..{head_sha}"])
    files = [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]
    return files

def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

# ---------------------- Diff validation ----------------------
def ensure_valid_unified_diff(patch: str) -> bool:
    if not patch:
        return False
    tokens = ("diff --git", "--- a/", "+++ b/", "@@")
    return all(t in patch for t in tokens)

def sanitize_patch_whitespace(patch: str) -> str:
    return re.sub(r"[ \t]+(\r?\n)", r"\1", patch)

def dump_rejects_as_comment():
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

# ---------------------- OpenAI ----------------------
def ask_model_for_patch(diff_text: str, pr_body: str, user_hint: str, file_context: List[Tuple[str, str]], attempt: int) -> str:
    try:
        from openai import OpenAI
    except Exception as e:
        comment(f"❌ OpenAI SDK import failed: {e}")
        sys.exit(0)

    client = OpenAI(api_key=OPENAI_API_KEY)

    system = (
        "You are a careful code refactoring assistant. "
        "Return a git unified diff that applies cleanly on top of HEAD. "
        "Only include changed hunks. No prose."
    )

    rules = """
Fix CropManage API endpoint integration using these rules:
1) List ranches: GET /v2/ranches.json
2) List plantings for a ranch (prefer): GET /v2/ranches/{Ranch_External_GUID}/plantings.json?active=true
   Fallback numeric: GET /v2/plantings/list-by-ranch.json?ranchId={numericId}&active=true
3) Ranch objects from /v2/ranches.json contain Name, Id, and may include Ranch_External_GUID.
4) Normalize ranch name comparisons with .strip().lower().
5) Do NOT produce whitespace-only diffs.
6) Return a valid unified diff ONLY; no explanations or extra text.
"""

    # Build context
    ctx = f"Pull Request description:\n{pr_body or '(empty)'}\n\n"
    ctx += f"Triggering comment:\n{user_hint or '(none)'}\n\n"
    ctx += "Base..Head unified diff:\n"
    ctx += diff_text

    # On retry, add file contents (helps the model construct correct hunks)
    if attempt > 1 and file_context:
        ctx += "\n\nChanged files (current HEAD content follows):\n"
        for path, content in file_context[:20]:  # cap for safety
            # keep each file body within a reasonable limit
            snippet = content if len(content) < 50000 else content[:50000]
            ctx += f"\n----- BEGIN FILE: {path} -----\n{snippet}\n----- END FILE: {path} -----\n"

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": rules + "\n\n" + ctx},
        ],
    )
    return (resp.choices[0].message.content or "")

# ---------------------- Apply patch ----------------------
def apply_patch_and_push(patch_text: str):
    tmp = Path(tempfile.gettempdir()) / "chat_fix.diff"
    tmp.write_text(patch_text, encoding="utf-8")

    # Try normal apply
    r1 = run(["git", "apply", "--whitespace=fix", str(tmp)])
    if r1.returncode != 0:
        log("Normal apply failed; trying 3-way merge...")
        # Try 3-way apply
        r2 = run(["git", "apply", "--3way", "--whitespace=fix", str(tmp)])
        if r2.returncode != 0:
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

    # Commit & push
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

    pr = get_pr()
    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]
    pr_body  = pr.get("body") or ""
    log(f"PR #{PR_NUMBER}: {REPO} base={base_sha[:7]} head={head_sha[:7]} (event={EVENT_NAME})")

    diff = get_unified_diff(base_sha, head_sha)
    if not diff.strip():
        comment("ℹ️ No changes to patch (diff is empty).")
        return

    changed_files = get_changed_files(base_sha, head_sha)
    file_ctx = [(p, read_file(p)) for p in changed_files]

    # Attempt 1: diff only + PR body + triggering comment
    patch = ask_model_for_patch(diff, pr_body, COMMENT_BODY, [], attempt=1)

    def valid(p): return ensure_valid_unified_diff(p)

    if not valid(patch):
        # Attempt 2: include file contents for context
        patch = ask_model_for_patch(diff, pr_body, COMMENT_BODY, file_ctx, attempt=2)

    if not valid(patch):
        comment("⚠️ Model did not return a valid unified diff. Skipping apply.\n\n```text\n"
                + patch[:65000] + "\n```")
        return

    patch = sanitize_patch_whitespace(patch)
    apply_patch_and_push(patch)

if __name__ == "__main__":
    main()
