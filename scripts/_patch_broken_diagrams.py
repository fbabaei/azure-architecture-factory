"""
One-shot script to patch old drawio files that use external image URLs
(learn.microsoft.com or svghandler) with styled rectangles that render
correctly in embed.diagrams.net without external resource loading.

Searches both azure-architecture-factory and any copilot-architecture-suite
mirror copies so all portals in the workspace are updated.
"""
import pathlib
import re

OLD_PATTERN = re.compile(
    r'style="shape=image;[^"]*image=https?://[^"]*"'
)
NEW_STYLE = (
    'style="rounded=1;whiteSpace=wrap;html=1;arcSize=15;'
    'fillColor=#0078D4;strokeColor=#FFFFFF40;fontColor=#FFFFFF;'
    'fontSize=13;fontStyle=1;verticalAlign=middle;align=center;"'
)

# Collect all roots to search: this repo + any known mirror paths
this_repo = pathlib.Path(__file__).parent.parent.resolve()
workspace_root = this_repo.parent  # e.g. c:\Users\...\workspace

search_roots = [this_repo]
for candidate in [
    workspace_root / "copilot-architecture-suite" / "apps" / "azure-architecture-factory",
    workspace_root / "copilot-architecture-suite" / "tools" / "azure-architecture-factory",
]:
    if candidate.is_dir():
        search_roots.append(candidate)

patched_total = 0
for root in search_roots:
    for f in root.rglob("*.drawio"):
        content = f.read_text(encoding="utf-8", errors="ignore")
        matches = OLD_PATTERN.findall(content)
        if not matches:
            continue
        new_content = OLD_PATTERN.sub(NEW_STYLE, content)
        f.write_text(new_content, encoding="utf-8")
        patched_total += len(matches)
        try:
            rel = f.relative_to(workspace_root)
        except ValueError:
            rel = f
        print(f"Patched {len(matches):>2} node(s) in {rel}")

print(f"\nTotal nodes patched: {patched_total}")
