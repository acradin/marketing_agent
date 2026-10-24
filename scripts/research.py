"""Read upstream metadata and small source files, without installing or executing upstream code."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1] / "docs" / "research-sources"
ROOT.mkdir(parents=True, exist_ok=True)
REPOS = ["NousResearch/hermes-agent", "socai-io/jev-social", "edgeaig/socialfetch", "yt-dlp/yt-dlp", "yassmin1/TrendRadar", "gitroomhq/postiz-app", "browser-use/browser-harness"]


def get(url):
    with urlopen(Request(url, headers={"User-Agent": "ViralEngineResearch/0.1"}), timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


result = []
for repo in REPOS:
    item = {"repository": "https://github.com/" + repo, "runtime_tested": False}
    try:
        metadata = json.loads(get("https://api.github.com/repos/" + repo))
        item.update({k: metadata.get(k) for k in ("pushed_at", "updated_at", "archived", "default_branch", "license")})
        branch = metadata["default_branch"]
        tree = json.loads(get(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"))
        paths = [x["path"] for x in tree.get("tree", []) if x["type"] == "blob"]
        candidates = [p for p in paths if p.lower() in ("readme.md", "license", "license.md", "pyproject.toml", "package.json")]
        code = [p for p in paths if p.endswith((".py", ".ts")) and any(s in p.lower() for s in ("cli", "scheduler", "tiktok", "reddit", "post.controller", "main.py"))]
        candidates += code[:2]
        item["files"] = []
        for path in candidates:
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
            try:
                content = get(url)
                target = ROOT / (repo.replace("/", "--") + "--" + path.replace("/", "--"))
                target.write_text(content, encoding="utf-8")
                item["files"].append({"url": url, "local": target.name})
            except Exception as exc:
                item.setdefault("file_errors", []).append({"path": path, "error": type(exc).__name__})
    except Exception as exc:
        item["error"] = type(exc).__name__
        item["files"] = []
        fallback = {
            "NousResearch/hermes-agent": ["README.md", "pyproject.toml", "LICENSE", "cron/scheduler.py"],
            "socai-io/jev-social": ["README.md", "package.json", "LICENSE", "src/cli.ts"],
            "edgeaig/socialfetch": ["README.md", "pyproject.toml", "LICENSE", "src/socialfetch/cli.py"],
            "yt-dlp/yt-dlp": ["README.md", "pyproject.toml", "LICENSE", "yt_dlp/extractor/tiktok.py"],
            "yassmin1/TrendRadar": ["README.md", "LICENSE", "main.py"],
            "gitroomhq/postiz-app": ["README.md", "package.json", "LICENSE", "apps/backend/src/api/routes/posts.controller.ts"],
            "browser-use/browser-harness": ["README.md", "pyproject.toml", "LICENSE", "src/browser_harness/cli.py"],
        }
        for path in fallback[repo]:
            url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
            try:
                content = get(url)
                target = ROOT / (repo.replace("/", "--") + "--" + path.replace("/", "--"))
                target.write_text(content, encoding="utf-8")
                item["files"].append({"url": url, "local": target.name})
            except Exception as error:
                item.setdefault("file_errors", []).append({"path": path, "error": type(error).__name__})
    result.append(item)
(ROOT.parent / "upstream-audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
