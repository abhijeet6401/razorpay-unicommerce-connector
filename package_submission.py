"""Generate an explicit, credential-free file attachment; never zip the workspace wholesale."""
from pathlib import Path
import json
import zipfile
from connector import TOOLS

ROOT = Path(__file__).resolve().parent
FILES = ["connector.py", "mock_store.py", "demo.py", "tests/test_connector.py", "run.ps1",
         "README.md", "AGENT_CAPABILITIES.md", "DEMO_GUIDE.md", "SUBMISSION.md", ".env.example",
         ".gitignore", "mcp-config.example.json", "tools.json", "demo-output.txt", "verification.txt",
         "package_submission.py", ".github/workflows/tests.yml"]


def main():
    (ROOT / "tools.json").write_text(json.dumps({"tools": TOOLS}, indent=2) + "\n", encoding="utf-8")
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Missing submission files: " + ", ".join(missing))
    with zipfile.ZipFile(ROOT / "submission.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, "unicommerce-connector/" + name)
    print("Created submission.zip with " + str(len(FILES)) + " explicitly selected files.")


if __name__ == "__main__":
    main()
