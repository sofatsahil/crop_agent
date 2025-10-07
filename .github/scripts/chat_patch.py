import os, sys, json, subprocess, requests, tempfile, textwrap
from pathlib import Path

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["REPO"]
PR_NUMBER = os.environ.get("PR_NUMBER")

# --- helpers ---------------------------------------------------------------
def gh_api(path, method="GET", **kwargs):
    url = f"https://api.github.com{path}"
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}",
               "Accept": "application/vnd.github+json"}
    r = requests.request(method, url, headers=headers, **kwargs)
    r.raise_for_status()
    return r

def get_pr_changed_files():
    r = gh_api(f"/repos/{REPO}/pulls/{PR_NUMBER}/files")
    return r.json()

def get_unified_diff():
    # produce a unified diff for the changed files against base
    r = gh_api(f"/repos/{REPO}/pulls/{PR_NUMBER}")
    pr = r.json()
    base_sha = pr["base"]["sha"]
    head_sha = pr["head"]["sha"]
    # Checkout already done by Actions; use git to diff
    diff = subprocess.check_output(["git", "diff", "--unified", f"{base_sha}..{head_sha}"]).decode("utf-8", "ignore")
    return diff

def ask_model_for_patch(diff_text):
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"""
You are a code refactoring assistant. Read this git unified diff (base..head) and return a new unified diff that:
- fixes CropManage API endpoints based on these rules:
  1) List ranches: GET /v2/ranches.json
  2) List plantings in a ranch: PREFER GET /v2/ranches/{{Ranch_External_GUID}}/plantings.json?active=true
     FALLBACK GET /v2/plantings/list-by-ranch.json?ranchId={{numericId}}&active=true
  3) Use exact field names from /v2/ranches.json: Name, Id, Ranch_External_GUID (when present).
- includes only the changed hunks needed.
- applies cleanly on top of the current head commit.

Input diff:
{diff_text}
"""
    # Chat Completions w/ text output returning just a diff
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content": prompt}],
        temperature=0.2
    )
    return resp.choices[0].message.content

def apply_patch_and_commit(patch_text, commit_msg="chore: apply chat-fix patch"):
    patch_file = Path(tempfile.gettempdir()) / "chat_patch.diff"
    patch_file.write_text(patch_text, encoding="utf-8")
    # apply; ignore whitespace noise
    subprocess.check_call(["git", "apply", "--whitespace=fix", str(patch_file)])
    subprocess.check_call(["git", "config", "user.name", "chat-fix-bot"])
    subprocess.check_call(["git", "config", "user.email", "actions@github.com"])
    subprocess.check_call(["git", "add", "-A"])
    subprocess.check_call(["git", "commit", "-m", commit_msg])
    subprocess.check_call(["git", "push"])

def comment(text):
    gh_api(f"/repos/{REPO}/issues/{PR_NUMBER}/comments",
           method="POST", json={"body": text})

# --- main ------------------------------------------------------------------
try:
    diff = get_unified_diff()
    if not diff.strip():
        comment("No changes to patch. (Diff is empty.)")
        sys.exit(0)
    patch = ask_model_for_patch(diff)
    if "diff --git" not in patch:
        comment("The model did not return a valid unified diff. Output:\n\n```\n"+patch+"\n```")
        sys.exit(0)
    apply_patch_and_commit(patch)
    comment("✅ Patch applied by Chat Fix Bot.")
except subprocess.CalledProcessError as e:
    comment(f"❌ Patch failed:\n```\n{e}\n```")
    raise
except requests.HTTPError as e:
    print(e.response.text)
    comment(f"❌ HTTP error: {e}")
    raise
except Exception as e:
    comment(f"❌ Unexpected error: {e}")
    raise
