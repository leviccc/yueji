"""Build an allowlisted deployment archive; never include credentials or databases."""
import hashlib
import tarfile
from pathlib import Path
from .bootstrap import ROOT


def main():
    output = ROOT / "output/integration-release.tar.gz"
    output.parent.mkdir(exist_ok=True)
    files = []
    for directory in ["integration", "data/测评书库", "a/backend", "a/examples", "b/static", "c/src/yueji_qa", "yueji-ui/dist"]:
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and not any(part in {"__pycache__", "tests"} for part in p.parts) and p.suffix != ".pyc" and not p.name.startswith('.env'))
    files.extend(p for p in (ROOT / "b").iterdir() if p.is_file() and (p.suffix == ".py" or p.name == "schema.sql"))
    files.extend(p for p in [ROOT / "README.md", ROOT / "c/THIRD_PARTY_NOTICES.md"] if p.exists())
    with tarfile.open(output, "w:gz") as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname=path.relative_to(ROOT), recursive=False)
    print(output)
    print("SHA256", hashlib.sha256(output.read_bytes()).hexdigest())
    print("FILES", len(set(files)))


if __name__ == "__main__":
    main()

