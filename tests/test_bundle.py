from __future__ import annotations

import ast
import math
import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "Variable Font Overlay.glyphsPlugin" / "Contents"


class BundleTests(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.source_tree = ast.parse(
			(BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		)

	@classmethod
	def reporter_method(cls, name):
		reporter_class = next(
			node
			for node in cls.source_tree.body
			if isinstance(node, ast.ClassDef)
			and node.name == "VariableFontOverlayPreview"
		)
		node = next(
			node
			for node in reporter_class.body
			if isinstance(node, ast.FunctionDef) and node.name == name
		)
		node.decorator_list = []
		namespace = {"math": math}
		exec(compile(ast.Module(body=[node], type_ignores=[]), "<method>", "exec"), namespace)
		return namespace[name]

	def test_principal_classes_match_source(self):
		with (BUNDLE / "Info.plist").open("rb") as handle:
			info = plistlib.load(handle)
		tree = ast.parse(
			(BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		)
		classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
		self.assertEqual(
			info["Principal Classes"],
			["VariableFontOverlayPreview", "VariableFontOverlayPalette"],
		)
		self.assertTrue(set(info["Principal Classes"]).issubset(classes))
		self.assertEqual(info["CFBundleName"], "Variable Font Overlay")
		self.assertEqual(info["CFBundleShortVersionString"], "1.2.0")

	def test_reporter_has_required_hooks(self):
		tree = ast.parse(
			(BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		)
		plugin_class = next(
			node
			for node in tree.body
			if isinstance(node, ast.ClassDef)
			and node.name == "VariableFontOverlayPreview"
		)
		methods = {
			node.name for node in plugin_class.body if isinstance(node, ast.FunctionDef)
		}
		self.assertTrue(
			{"settings", "start", "foreground", "inactiveLayerForeground"}
			.issubset(methods)
		)

	def test_palette_has_required_hooks(self):
		tree = ast.parse(
			(BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		)
		palette_class = next(
			node
			for node in tree.body
			if isinstance(node, ast.ClassDef)
			and node.name == "VariableFontOverlayPalette"
		)
		methods = {
			node.name for node in palette_class.body if isinstance(node, ast.FunctionDef)
		}
		self.assertTrue({"settings", "start", "update"}.issubset(methods))

	def test_launcher_is_executable(self):
		launcher = BUNDLE / "MacOS" / "plugin"
		self.assertTrue(launcher.stat().st_mode & 0o111)

	def test_registered_axis_steps_are_natural(self):
		smart_step = self.reporter_method("_smart_step")

		class Axis:
			def __init__(self, tag):
				self.axisTag = tag

		self.assertEqual(smart_step(None, Axis("wght"), 100, 900), 1.0)
		self.assertEqual(smart_step(None, Axis("wdth"), 50, 200), 1.0)
		self.assertEqual(smart_step(None, Axis("opsz"), 8, 144), 1.0)
		self.assertEqual(smart_step(None, Axis("slnt"), -12, 0), 0.1)

	def test_custom_axis_step_targets_about_two_hundred_stops(self):
		smart_step = self.reporter_method("_smart_step")

		class Axis:
			axisTag = "TEST"

		step = smart_step(None, Axis(), 0, 1)
		self.assertEqual(step, 0.005)
		self.assertLessEqual(1 / step, 250)

	def test_palette_uses_dynamic_height_without_nested_scroll_view(self):
		source = (BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		self.assertIn("self._desired_height = 104.0 + row_count * row_height", source)
		self.assertIn("self._height_constraint.setConstant_", source)
		self.assertNotIn("NSScrollView", source)

	def test_overlay_preferences_use_glyphs_defaults(self):
		source = (BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		self.assertIn("com.alikia.VariableFontOverlay.opacity", source)
		self.assertIn("com.alikia.VariableFontOverlay.color", source)
		self.assertIn("Glyphs.registerDefault(_OPACITY_DEFAULT_KEY", source)
		self.assertIn("Glyphs.defaults[_COLOR_DEFAULT_KEY] =", source)


if __name__ == "__main__":
	unittest.main()
