from __future__ import annotations

import ast
import math
import plistlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "Variable Font Overlay.glyphsPlugin" / "Contents"
FONT_STATE_ATTRIBUTES = (
	"_font_signature",
	"_axes",
	"_axis_bounds",
	"_axis_steps",
	"_axis_values",
	"_instance",
	"_proxy",
	"_interpolated_font",
)


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
		namespace = {
			"math": math,
			"_FONT_STATE_ATTRIBUTES": FONT_STATE_ATTRIBUTES,
		}
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
		self.assertEqual(info["CFBundleShortVersionString"], "1.2.3")

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

	def test_component_glyphs_use_component_aware_full_interpolation(self):
		source = (BUNDLE / "Resources" / "plugin.py").read_text(encoding="utf-8")
		self.assertIn("self._instance.interpolatedFont", source)
		self.assertIn('"drawBezierPath"', source)
		self.assertIn('"drawOpenBezierPath"', source)
		self.assertIn("result.appendBezierPath_(path)", source)
		self.assertNotIn("layer.decomposeComponents()", source)
		self.assertNotIn("preview_layer.completeBezierPath", source)

	def test_component_drawing_path_includes_components(self):
		drawing_path = self.reporter_method("_drawing_path")

		class Path:
			def __init__(self, name=None):
				self.name = name
				self.appended = []

			def isEmpty(self):
				return False

			def appendBezierPath_(self, path):
				self.appended.append(path.name)

		class BezierPathFactory:
			@staticmethod
			def bezierPath():
				return Path()

		drawing_path.__globals__["NSBezierPath"] = BezierPathFactory

		class Component:
			def __init__(self, name):
				self.bezierPath = Path(name)

		class Layer:
			components = [Component("dot"), Component("accent")]

			def drawBezierPath(self):
				raise AssertionError("must not render Glyphs placeholders")

			bezierPath = Path("outline")

		class Reporter:
			@staticmethod
			def _layer_has_components(layer):
				return bool(layer.components)

		result = drawing_path(
			Reporter(),
			Layer(),
			"drawBezierPath",
			"bezierPath",
		)
		self.assertEqual(result.appended, ["outline", "dot", "accent"])

	def test_empty_component_path_is_skipped_without_placeholder(self):
		drawing_path = self.reporter_method("_drawing_path")

		class Path:
			def __init__(self):
				self.appended = 0

			def isEmpty(self):
				return False

			def appendBezierPath_(self, path):
				self.appended += 1

		class BezierPathFactory:
			@staticmethod
			def bezierPath():
				return Path()

		drawing_path.__globals__["NSBezierPath"] = BezierPathFactory

		class EmptyComponent:
			@property
			def bezierPath(self):
				raise RuntimeError("empty base glyph")

		class Layer:
			components = [EmptyComponent()]
			bezierPath = None

			@property
			def drawBezierPath(self):
				raise AssertionError("must not render Glyphs placeholders")

		class Reporter:
			@staticmethod
			def _layer_has_components(layer):
				return True

		result = drawing_path(
			Reporter(),
			Layer(),
			"drawBezierPath",
			"bezierPath",
		)
		self.assertEqual(result.appended, 0)

	def test_document_state_is_restored_per_font(self):
		store_state = self.reporter_method("_store_current_font_state")
		restore_state = self.reporter_method("_restore_font_state")

		class Reporter:
			pass

		reporter = Reporter()
		reporter._font_states = {}
		font_a = object()
		font_b = object()
		reporter._font = font_a
		for attribute in FONT_STATE_ATTRIBUTES:
			setattr(reporter, attribute, [attribute, "a"])
		reporter._font_signature = ("axis-a",)
		store_state(reporter)

		reporter._font = font_b
		reporter._axis_values = ["b"]
		self.assertTrue(restore_state(reporter, font_a, ("axis-a",)))
		self.assertIs(reporter._font, font_a)
		self.assertEqual(reporter._axis_values, ["_axis_values", "a"])

	def test_stale_axis_index_is_ignored(self):
		set_axis_value = self.reporter_method("_set_axis_value")

		class Reporter:
			_axis_bounds = [(0, 100)]

		self.assertIsNone(set_axis_value(Reporter(), 3, 50))


if __name__ == "__main__":
	unittest.main()
