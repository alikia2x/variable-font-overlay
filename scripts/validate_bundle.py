#!/usr/bin/env python3
"""Static validation for the Glyphs Reporter bundle."""

from __future__ import annotations

import ast
import plistlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "Variable Font Overlay.glyphsPlugin"
CONTENTS = BUNDLE / "Contents"
PLIST = CONTENTS / "Info.plist"
EXECUTABLE = CONTENTS / "MacOS" / "plugin"
PLUGIN = CONTENTS / "Resources" / "plugin.py"


def fail(message: str) -> None:
	print(f"ERROR: {message}", file=sys.stderr)
	raise SystemExit(1)


def main() -> None:
	for path in (BUNDLE, PLIST, EXECUTABLE, PLUGIN):
		if not path.exists():
			fail(f"missing {path.relative_to(ROOT)}")

	with PLIST.open("rb") as handle:
		info = plistlib.load(handle)

	required = {"CFBundleExecutable": "plugin"}
	for key, expected in required.items():
		if info.get(key) != expected:
			fail(f"{key} must be {expected!r}, got {info.get(key)!r}")

	source = PLUGIN.read_text(encoding="utf-8")
	if "____" in source or "____" in PLIST.read_text(encoding="utf-8"):
		fail("unreplaced SDK placeholder found")
	tree = ast.parse(source, filename=str(PLUGIN))
	class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
	principal_classes = info.get("Principal Classes", [])
	if principal_classes != [
		"VariableFontOverlayPreview",
		"VariableFontOverlayPalette",
	]:
		fail("Principal Classes must list the Reporter and Palette")
	for class_name in principal_classes:
		if class_name not in class_names:
			fail(f"principal class {class_name} does not match a Python class")

	method_names = {
		node.name
		for node in ast.walk(tree)
		if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
	}
	for method in (
		"settings",
		"foreground",
		"inactiveLayerForeground",
		"_smart_step",
	):
		if method not in method_names:
			fail(f"Reporter method {method} is missing")

	magic = EXECUTABLE.read_bytes()[:4]
	# FAT_MAGIC (big endian) or FAT_CIGAM. The official SDK launcher is universal.
	if magic not in (b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
		fail("Contents/MacOS/plugin is not a universal Mach-O launcher")
	if not EXECUTABLE.stat().st_mode & 0o111:
		fail("Contents/MacOS/plugin is not executable")

	print("OK: Glyphs plugin structure, principal classes, Python source, and launcher")


if __name__ == "__main__":
	main()
