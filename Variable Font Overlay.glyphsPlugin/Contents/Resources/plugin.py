# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import math
import objc
import traceback

from AppKit import (
	NSButton,
	NSButtonTypeSwitch,
	NSBezierPath,
	NSColor,
	NSColorWell,
	NSControlSizeSmall,
	NSControlStateValueOff,
	NSControlStateValueOn,
	NSEventModifierFlagControl,
	NSEventModifierFlagOption,
	NSFont,
	NSLayoutAttributeHeight,
	NSLayoutAttributeNotAnAttribute,
	NSLayoutConstraint,
	NSLayoutRelationEqual,
	NSMakeRect,
	NSMakeSize,
	NSSlider,
	NSTextField,
	NSView,
	NSViewMinXMargin,
	NSViewWidthSizable,
)
from GlyphsApp import Glyphs, GSInstance, UPDATEINTERFACE
from GlyphsApp.plugins import PalettePlugin, ReporterPlugin


_REPORTER = None
_OPACITY_DEFAULT_KEY = "com.alikia.VariableFontOverlay.opacity"
_COLOR_DEFAULT_KEY = "com.alikia.VariableFontOverlay.color"
_FONT_STATE_ATTRIBUTES = (
	"_font_signature",
	"_axes",
	"_axis_bounds",
	"_axis_steps",
	"_axis_values",
	"_instance",
	"_proxy",
	"_interpolated_font",
)


def _localized(english, chinese):
	return Glyphs.localize({
		"en": english,
		"zh": chinese,
		"zh-Hans": chinese,
	})


def _reporter_instance():
	global _REPORTER
	if _REPORTER is not None:
		return _REPORTER
	for reporter in Glyphs.reporters:
		if reporter.__class__.__name__ == "VariableFontOverlayPreview":
			_REPORTER = reporter
			return reporter
	return None


class VariableFontOverlayPreview(ReporterPlugin):
	"""Draw the interpolation overlay; controls live in the right Palette."""

	@objc.python_method
	def settings(self):
		self.menuName = _localized(
			"Variable Font Overlay",
			"可变字体叠加",
		)
		self.keyboardShortcut = "v"
		self.keyboardShortcutModifier = (
			NSEventModifierFlagControl | NSEventModifierFlagOption
		)
		self.generalContextMenus = [{
			"name": _localized(
				"Reset Preview to Current Master",
				"重置到当前母版",
			),
			"action": self.resetAxes_,
		}]

	@objc.python_method
	def start(self):
		global _REPORTER
		_REPORTER = self
		Glyphs.registerDefault(_OPACITY_DEFAULT_KEY, 0.34)
		Glyphs.registerDefault(
			_COLOR_DEFAULT_KEY,
			[0.05, 0.58, 0.95, 1.0],
		)
		self._font = None
		self._font_signature = None
		self._axes = []
		self._axis_bounds = []
		self._axis_steps = []
		self._axis_values = []
		self._instance = None
		self._proxy = None
		self._interpolated_font = None
		self._font_states = {}
		self._opacity = self._load_opacity()
		self._overlay_color = self._load_color()
		self._last_error = None
		self._active = False

	@objc.python_method
	def _load_opacity(self):
		try:
			value = float(Glyphs.defaults[_OPACITY_DEFAULT_KEY])
			return min(max(value, 0.05), 0.85)
		except Exception:
			return 0.34

	@objc.python_method
	def _load_color(self):
		try:
			components = Glyphs.defaults[_COLOR_DEFAULT_KEY]
			if components is not None and len(components) >= 3:
				alpha = float(components[3]) if len(components) > 3 else 1.0
				return NSColor.colorWithCalibratedRed_green_blue_alpha_(
					float(components[0]),
					float(components[1]),
					float(components[2]),
					alpha,
				)
		except Exception:
			pass
		return NSColor.colorWithCalibratedRed_green_blue_alpha_(
			0.05, 0.58, 0.95, 1.0
		)

	def willActivate(self):
		try:
			objc.super(VariableFontOverlayPreview, self).willActivate()
		except Exception:
			pass
		self._active = True
		try:
			self._sync_font(Glyphs.font)
		except Exception:
			self._report_error("Could not prepare interpolation")
		Glyphs.redraw()

	def willDeactivate(self):
		self._active = False
		self._proxy = None
		self._interpolated_font = None
		self._store_current_font_state()
		try:
			objc.super(VariableFontOverlayPreview, self).willDeactivate()
		except Exception:
			pass
		Glyphs.redraw()

	@objc.python_method
	def foreground(self, layer):
		self._draw_interpolation(layer)

	@objc.python_method
	def inactiveLayerForeground(self, layer):
		self._draw_interpolation(layer)

	@objc.python_method
	def _draw_interpolation(self, source_layer):
		try:
			font = self._font_for_layer(source_layer)
			if font is None or source_layer is None or source_layer.parent is None:
				return
			if self._font_changed(font):
				self._sync_font(font)
			if not self._axes or self._instance is None:
				return

			preview_layer = self._interpolated_layer(source_layer.parent.name)
			if preview_layer is None:
				return

			self._overlay_color.colorWithAlphaComponent_(self._opacity).set()
			closed_path = self._drawing_path(
				preview_layer,
				"drawBezierPath",
				"bezierPath",
			)
			if closed_path is not None and not closed_path.isEmpty():
				closed_path.fill()

			open_path = self._drawing_path(
				preview_layer,
				"drawOpenBezierPath",
				"openBezierPath",
			)
			if open_path is not None and not open_path.isEmpty():
				scale = max(float(self.getScale()), 0.001)
				open_path.setLineWidth_(max(0.5, 1.25 / scale))
				open_path.stroke()
			self._last_error = None
		except Exception:
			self._report_error("Interpolation failed")

	@objc.python_method
	def _interpolated_layer(self, glyph_name):
		proxy_layer = self._proxy_layer(glyph_name)
		if proxy_layer is None:
			return None
		if self._layer_has_components(proxy_layer):
			return self._component_safe_interpolated_layer(glyph_name)
		return proxy_layer

	@objc.python_method
	def _proxy_layer(self, glyph_name):
		if self._proxy is None:
			self._proxy = self._instance.interpolatedFontProxy
		if self._proxy is None:
			return None

		glyph = self._proxy.glyphs[glyph_name]
		if glyph is None:
			return None
		try:
			master_id = self._proxy.fontMaster().id
		except Exception:
			try:
				master_id = self._proxy.fontMasterID()
			except Exception:
				master_id = self._proxy.masters[0].id
		return glyph.layers[master_id]

	@objc.python_method
	def _layer_has_components(self, layer):
		try:
			return len(layer.components) > 0
		except Exception:
			return False

	@objc.python_method
	def _component_safe_interpolated_layer(self, glyph_name):
		"""Use a full interpolation for component glyphs.

		The proxy can leave component references unresolved at synthetic
		designspace locations, which makes Glyphs draw an Empty Base Glyph
		placeholder. A full interpolated font resolves valid component
		references; drawing later merges their actual paths without asking
		Glyphs to synthesize placeholders for unresolved ones.
		"""
		if self._interpolated_font is None:
			try:
				self._interpolated_font = self._instance.interpolatedFont
			except Exception:
				self._interpolated_font = (
					self._instance.pyobjc_instanceMethods.interpolatedFont()
				)
		if self._interpolated_font is None:
			return None

		glyph = self._interpolated_font.glyphs[glyph_name]
		if glyph is None:
			return None
		try:
			layer = glyph.layers[0]
		except Exception:
			layers = list(glyph.layers)
			layer = layers[0] if layers else None
		if layer is None:
			return None
		return layer

	@objc.python_method
	def _drawing_path(self, layer, drawing_attribute, fallback_attribute):
		if self._layer_has_components(layer):
			# Do not ask GSLayer.drawBezierPath to resolve components here.
			# Glyphs renders an "Empty Base Glyph" placeholder when one of
			# those references is empty. Component paths, on the other hand,
			# contain only geometry that could actually be resolved and are
			# already transformed into the parent layer's coordinates.
			result = NSBezierPath.bezierPath()
			owners = [layer]
			try:
				owners.extend(list(layer.components))
			except Exception:
				pass
			for owner in owners:
				try:
					path = getattr(owner, fallback_attribute)
					path = path() if callable(path) else path
					if path is not None and not path.isEmpty():
						result.appendBezierPath_(path)
				except Exception:
					continue
			return result

		try:
			path = getattr(layer, drawing_attribute)
			return path() if callable(path) else path
		except Exception:
			pass
		try:
			return getattr(layer, fallback_attribute)
		except Exception:
			return None

	@objc.python_method
	def _font_for_layer(self, layer):
		try:
			glyph = layer.parent
			font = glyph.parent
			return font() if callable(font) else font
		except Exception:
			return Glyphs.font

	@objc.python_method
	def _store_current_font_state(self):
		if self._font is None:
			return
		state = {"font": self._font}
		for attribute in _FONT_STATE_ATTRIBUTES:
			state[attribute] = getattr(self, attribute)
		self._font_states[id(self._font)] = state

	@objc.python_method
	def _restore_font_state(self, font, signature):
		state = self._font_states.get(id(font))
		if (
			state is None
			or state.get("font") is not font
			or state.get("_font_signature") != signature
		):
			return False
		self._font = font
		for attribute in _FONT_STATE_ATTRIBUTES:
			setattr(self, attribute, state[attribute])
		return True

	@objc.python_method
	def _font_changed(self, font):
		if font is None:
			return self._font is not None
		return (
			font != self._font
			or self._signature_for_font(font) != self._font_signature
		)

	@objc.python_method
	def _signature_for_font(self, font):
		return tuple(
			(
				str(self._axis_identifier(axis, index)),
				str(getattr(axis, "name", "")),
				str(getattr(axis, "axisTag", "")),
			)
			for index, axis in enumerate(font.axes)
		)

	@objc.python_method
	def _sync_font(self, font):
		if self._font is not None and self._font is not font:
			self._store_current_font_state()

		if font is not None:
			signature = self._signature_for_font(font)
			if self._restore_font_state(font, signature):
				return

		self._font = font
		self._proxy = None
		self._instance = None
		self._axes = []
		self._axis_bounds = []
		self._axis_steps = []
		self._axis_values = []
		self._font_signature = None
		self._interpolated_font = None

		if font is None:
			return

		self._axes = list(font.axes)
		self._font_signature = self._signature_for_font(font)
		for index, axis in enumerate(self._axes):
			master_values = [
				self._axis_value(master, axis, index)
				for master in font.masters
			]
			master_values = [
				value for value in master_values if value is not None
			]
			if master_values:
				minimum, maximum = min(master_values), max(master_values)
			else:
				minimum, maximum = 0.0, 1.0
			if math.isclose(minimum, maximum):
				maximum = minimum + 1.0
			self._axis_bounds.append((minimum, maximum))
			self._axis_steps.append(
				self._smart_step(axis, minimum, maximum)
			)

			selected_master = getattr(font, "selectedFontMaster", None)
			value = self._axis_value(selected_master, axis, index)
			if value is None:
				value = (minimum + maximum) * 0.5
			self._axis_values.append(
				self._quantize(value, minimum, maximum, self._axis_steps[-1])
			)

		if self._axes:
			self._instance = GSInstance()
			self._instance.font = font
			self._apply_axis_values()
		self._store_current_font_state()

	@objc.python_method
	def _smart_step(self, axis, minimum, maximum):
		"""Return a useful interaction step, targeting roughly 100–250 stops."""
		span = abs(float(maximum) - float(minimum))
		tag = str(getattr(axis, "axisTag", "") or "").lower()

		semantic_steps = {
			"wght": 1.0,
			"wdth": 1.0,
			"opsz": 1.0,
			"ital": 1.0,
			"grad": 1.0,
			"slnt": 0.1,
		}
		semantic = semantic_steps.get(tag)
		if semantic is not None and span >= semantic:
			return semantic
		if span <= 0.0:
			return 1.0

		raw = span / 200.0
		exponent = math.floor(math.log10(raw))
		fraction = raw / (10.0 ** exponent)
		if fraction <= 1.0:
			nice_fraction = 1.0
		elif fraction <= 2.0:
			nice_fraction = 2.0
		elif fraction <= 5.0:
			nice_fraction = 5.0
		else:
			nice_fraction = 10.0
		return nice_fraction * (10.0 ** exponent)

	@objc.python_method
	def _quantized_axis_value(self, index, value):
		minimum, maximum = self._axis_bounds[index]
		return self._quantize(
			value, minimum, maximum, self._axis_steps[index]
		)

	@objc.python_method
	def _quantize(self, value, minimum, maximum, step):
		value = self._clamp(value, minimum, maximum)
		if step <= 0:
			return value
		step_count = round((value - minimum) / step)
		value = minimum + step_count * step
		# Remove binary floating-point noise without discarding useful fractions.
		return round(self._clamp(value, minimum, maximum), 8)

	@objc.python_method
	def _axis_value(self, owner, axis, index):
		if owner is None:
			return None
		try:
			return float(
				owner.internalAxesValues[self._axis_identifier(axis, index)]
			)
		except Exception:
			pass
		try:
			return float(owner.internalAxesValues[index])
		except Exception:
			pass
		try:
			return float(owner.axes[index])
		except Exception:
			return None

	@objc.python_method
	def _axis_identifier(self, axis, index):
		for attribute in ("axisId", "id"):
			try:
				value = getattr(axis, attribute)
				if value is not None:
					return value
			except Exception:
				pass
		return index

	@objc.python_method
	def _apply_axis_values(self):
		if self._instance is None:
			return
		for index, (axis, value) in enumerate(
			zip(self._axes, self._axis_values)
		):
			try:
				axis_id = self._axis_identifier(axis, index)
				self._instance.internalAxesValues[axis_id] = value
			except Exception:
				self._instance.internalAxesValues[index] = value
		self._proxy = None
		self._interpolated_font = None
		self._store_current_font_state()

	@objc.python_method
	def _set_axis_value(self, index, value):
		if index < 0 or index >= len(self._axis_bounds):
			return None
		value = self._quantized_axis_value(index, value)
		self._axis_values[index] = value
		self._apply_axis_values()
		Glyphs.redraw()
		return value

	def resetAxes_(self, sender):
		self._reset_axes_for_font(Glyphs.font)

	@objc.python_method
	def _reset_axes_for_font(self, font):
		if font is None:
			return
		if self._font_changed(font):
			self._sync_font(font)
		master = getattr(font, "selectedFontMaster", None)
		for index, axis in enumerate(self._axes):
			value = self._axis_value(master, axis, index)
			if value is None:
				value = self._axis_bounds[index][0]
			self._axis_values[index] = self._quantized_axis_value(index, value)
		self._apply_axis_values()
		Glyphs.redraw()

	@objc.python_method
	def _format_axis_value(self, index, value):
		step = self._axis_steps[index]
		minimum = self._axis_bounds[index][0]
		decimals = max(
			self._decimal_places(step),
			self._decimal_places(minimum),
		)
		decimals = min(decimals, 6)
		if decimals == 0:
			return str(int(round(value)))
		return ("%.*f" % (decimals, value)).rstrip("0").rstrip(".")

	@objc.python_method
	def _decimal_places(self, value):
		text = ("%.8f" % abs(float(value))).rstrip("0")
		return len(text.split(".")[1]) if "." in text else 0

	@objc.python_method
	def _format_step(self, index):
		return self._format_axis_value(index, self._axis_steps[index])

	@objc.python_method
	def _clamp(self, value, minimum, maximum):
		return min(max(float(value), float(minimum)), float(maximum))

	@objc.python_method
	def _report_error(self, prefix):
		detail = traceback.format_exc()
		message = "%s: %s" % (prefix, detail.strip().splitlines()[-1])
		if message != self._last_error:
			self._last_error = message
			self.logToConsole(detail)

	@objc.python_method
	def __file__(self):
		return __file__


class VariableFontOverlayPalette(PalettePlugin):
	"""Compact controls embedded in the right Glyphs Palette."""

	@objc.python_method
	def settings(self):
		self.name = _localized(
			"Variable Font Overlay",
			"可变字体叠加",
		)
		# The Palette grows with its axes. Glyphs' sidebar handles scrolling.
		self.min = 145
		self.max = 1200
		self.sortId = 40
		self._ui_font = None
		self._ui_signature = None
		self._axis_sliders = {}
		self._axis_fields = {}
		self._axis_views = []
		self._desired_height = 153

		width, height = 232.0, self._desired_height
		self.dialog = NSView.alloc().initWithFrame_(
			NSMakeRect(0, 0, width, height)
		)
		self.dialog.setTranslatesAutoresizingMaskIntoConstraints_(False)
		self._height_constraint = (
			NSLayoutConstraint
			.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
				self.dialog,
				NSLayoutAttributeHeight,
				NSLayoutRelationEqual,
				None,
				NSLayoutAttributeNotAnAttribute,
				1.0,
				height,
			)
		)
		self.dialog.addConstraint_(self._height_constraint)
		self._build_static_controls(width, height)

	@objc.python_method
	def start(self):
		Glyphs.addCallback(self.update, UPDATEINTERFACE)
		self.update(None)

	@objc.typedSelector(b"L@:")
	def currentHeight(self):
		return int(self._desired_height)

	@objc.python_method
	def __del__(self):
		try:
			Glyphs.removeCallback(self.update)
		except Exception:
			pass

	@objc.python_method
	def _build_static_controls(self, width, height):
		self._toggle = NSButton.alloc().initWithFrame_(
			NSMakeRect(8, height - 30, width - 16, 22)
		)
		self._toggle.setButtonType_(NSButtonTypeSwitch)
		self._toggle.setControlSize_(NSControlSizeSmall)
		self._toggle.setTitle_(_localized("Show overlay", "显示叠加预览"))
		self._toggle.setTarget_(self)
		self._toggle.setAction_("togglePreview:")
		self._toggle.setAutoresizingMask_(NSViewWidthSizable)
		self.dialog.addSubview_(self._toggle)

		self._opacity_label = self._label(
			_localized("Opacity", "透明度"),
			NSMakeRect(8, 48, 50, 17),
			10.0,
		)
		self.dialog.addSubview_(self._opacity_label)

		self._opacity_slider = NSSlider.alloc().initWithFrame_(
			NSMakeRect(56, 46, width - 115, 20)
		)
		self._opacity_slider.setMinValue_(0.0)
		self._opacity_slider.setMaxValue_(1)
		self._opacity_slider.setControlSize_(NSControlSizeSmall)
		self._opacity_slider.setContinuous_(True)
		self._opacity_slider.setTarget_(self)
		self._opacity_slider.setAction_("opacityChanged:")
		self._opacity_slider.setAutoresizingMask_(NSViewWidthSizable)
		self.dialog.addSubview_(self._opacity_slider)

		self._color_well = NSColorWell.alloc().initWithFrame_(
			NSMakeRect(width - 50, 43, 42, 25)
		)
		self._color_well.setTarget_(self)
		self._color_well.setAction_("colorChanged:")
		self._color_well.setControlSize_(NSControlSizeSmall)
		self._color_well.setAutoresizingMask_(NSViewMinXMargin)
		self.dialog.addSubview_(self._color_well)

		self._reset_button = NSButton.alloc().initWithFrame_(
			NSMakeRect(8, 10, width - 16, 27)
		)
		self._reset_button.setTitle_(
			_localized("Reset to Current Master", "重置到当前母版")
		)
		self._reset_button.setBezelStyle_(1)
		self._reset_button.setControlSize_(NSControlSizeSmall)
		self._reset_button.setTarget_(self)
		self._reset_button.setAction_("resetAxes:")
		self._reset_button.setAutoresizingMask_(NSViewWidthSizable)
		self.dialog.addSubview_(self._reset_button)

	@objc.python_method
	def update(self, sender):
		try:
			reporter = _reporter_instance()
			font = self._font_for_palette()
			if reporter is None:
				return
			if font is not None and reporter._font_changed(font):
				reporter._sync_font(font)

			if (
				font != self._ui_font
				or reporter._font_signature != self._ui_signature
			):
				self._ui_font = font
				self._ui_signature = reporter._font_signature
				self._rebuild_axis_controls(reporter)
			self._sync_controls(reporter)
		except Exception:
			reporter = _reporter_instance()
			if reporter is not None:
				reporter._report_error("Palette update failed")

	@objc.python_method
	def _font_for_palette(self):
		controller = self.windowController()
		if controller is None:
			return Glyphs.font
		try:
			document = controller.document()
			font = document.font
			return font() if callable(font) else font
		except Exception:
			return Glyphs.font

	@objc.python_method
	def _reporter_for_palette(self):
		reporter = _reporter_instance()
		if reporter is None:
			return None
		font = self._font_for_palette()
		if font is not None and reporter._font_changed(font):
			reporter._sync_font(font)
		return reporter

	@objc.python_method
	def _rebuild_axis_controls(self, reporter):
		for view in self._axis_views:
			view.removeFromSuperview()
		self._axis_views = []
		self._axis_sliders = {}
		self._axis_fields = {}

		width = max(self.dialog.frame().size.width, 180.0)
		row_height = 49.0
		row_count = max(1, len(reporter._axes))
		self._desired_height = 104.0 + row_count * row_height
		self._height_constraint.setConstant_(self._desired_height)
		self.dialog.setFrameSize_(
			NSMakeSize(width, self._desired_height)
		)
		self._layout_static_controls(width, self._desired_height)

		if not reporter._axes:
			message = self._label(
				_localized(
					"The current font has no variation axes.",
					"当前字体没有可变轴。",
				),
				NSMakeRect(10, self._desired_height - 72, width - 20, 22),
				10.0,
			)
			message.setTextColor_(NSColor.secondaryLabelColor())
			message.setAutoresizingMask_(NSViewWidthSizable)
			self.dialog.addSubview_(message)
			self._axis_views.append(message)
			return

		cursor = self._desired_height - 38.0
		for index, axis in enumerate(reporter._axes):
			y = cursor - (index + 1) * row_height
			name = getattr(axis, "name", "") or ("Axis %d" % (index + 1))
			tag = getattr(axis, "axisTag", "") or ""
			minimum, maximum = reporter._axis_bounds[index]
			range_text = "%s–%s" % (
				reporter._format_axis_value(index, minimum),
				reporter._format_axis_value(index, maximum),
			)
			label_text = "%s · %s  %s" % (name, tag, range_text)
			label = self._label(
				label_text,
				NSMakeRect(10, y + 28, width - 20, 16),
				10.0,
			)
			label.setAutoresizingMask_(NSViewWidthSizable)
			self.dialog.addSubview_(label)
			self._axis_views.append(label)

			field_width = 54.0
			slider = NSSlider.alloc().initWithFrame_(
				NSMakeRect(10, y + 4, width - field_width - 28, 20)
			)
			slider.setMinValue_(minimum)
			slider.setMaxValue_(maximum)
			slider.setControlSize_(NSControlSizeSmall)
			slider.setContinuous_(True)
			slider.setTag_(index)
			slider.setTarget_(self)
			slider.setAction_("axisChanged:")
			slider.setAutoresizingMask_(NSViewWidthSizable)
			try:
				slider.setAltIncrementValue_(reporter._axis_steps[index])
			except Exception:
				pass
			step_tip = _localized("Step: ", "步进：") + reporter._format_step(index)
			slider.setToolTip_(step_tip)
			self._axis_sliders[index] = slider
			self.dialog.addSubview_(slider)
			self._axis_views.append(slider)

			field = self._field(
				"",
				NSMakeRect(width - field_width - 8, y + 2, field_width, 24),
			)
			field.setTag_(index)
			field.setTarget_(self)
			field.setAction_("axisFieldChanged:")
			field.setToolTip_(step_tip)
			field.setAutoresizingMask_(NSViewMinXMargin)
			self._axis_fields[index] = field
			self.dialog.addSubview_(field)
			self._axis_views.append(field)
		self.dialog.setNeedsLayout_(True)

	@objc.python_method
	def _layout_static_controls(self, width, height):
		self._toggle.setFrame_(NSMakeRect(8, height - 30, width - 16, 22))
		self._opacity_label.setFrame_(NSMakeRect(8, 48, 50, 17))
		self._opacity_slider.setFrame_(
			NSMakeRect(56, 46, width - 115, 20)
		)
		self._color_well.setFrame_(NSMakeRect(width - 50, 43, 42, 25))
		self._reset_button.setFrame_(NSMakeRect(8, 10, width - 16, 27))

	@objc.python_method
	def _sync_controls(self, reporter):
		active = any(
			item.__class__.__name__ == "VariableFontOverlayPreview"
			for item in Glyphs.activeReporters
		)
		self._toggle.setState_(
			NSControlStateValueOn if active else NSControlStateValueOff
		)
		self._opacity_slider.setDoubleValue_(reporter._opacity)
		self._color_well.setColor_(reporter._overlay_color)

		for index, value in enumerate(reporter._axis_values):
			slider = self._axis_sliders.get(index)
			field = self._axis_fields.get(index)
			if slider is not None:
				slider.setDoubleValue_(value)
			if field is not None:
				field.setStringValue_(
					reporter._format_axis_value(index, value)
				)

	@objc.python_method
	def _label(self, text, frame, size):
		field = NSTextField.alloc().initWithFrame_(frame)
		field.setStringValue_(text)
		field.setEditable_(False)
		field.setSelectable_(False)
		field.setBezeled_(False)
		field.setDrawsBackground_(False)
		field.setFont_(NSFont.systemFontOfSize_(size))
		return field

	@objc.python_method
	def _field(self, text, frame):
		field = NSTextField.alloc().initWithFrame_(frame)
		field.setStringValue_(text)
		field.setAlignment_(2)
		field.setFont_(NSFont.systemFontOfSize_(11.0))
		field.setControlSize_(NSControlSizeSmall)
		return field

	def togglePreview_(self, sender):
		reporter = _reporter_instance()
		if reporter is None:
			return
		if sender.state() == NSControlStateValueOn:
			Glyphs.activateReporter(reporter)
		else:
			Glyphs.deactivateReporter(reporter)

	def axisChanged_(self, sender):
		reporter = self._reporter_for_palette()
		if reporter is None:
			return
		index = int(sender.tag())
		value = reporter._set_axis_value(index, sender.doubleValue())
		if value is None:
			self.update(None)
			return
		sender.setDoubleValue_(value)
		field = self._axis_fields.get(index)
		if field is not None:
			field.setStringValue_(
				reporter._format_axis_value(index, value)
			)

	def axisFieldChanged_(self, sender):
		reporter = self._reporter_for_palette()
		if reporter is None:
			return
		index = int(sender.tag())
		if index < 0 or index >= len(reporter._axis_values):
			self.update(None)
			return
		try:
			value = float(sender.stringValue())
		except (TypeError, ValueError):
			value = reporter._axis_values[index]
		value = reporter._set_axis_value(index, value)
		if value is None:
			self.update(None)
			return
		slider = self._axis_sliders.get(index)
		if slider is not None:
			slider.setDoubleValue_(value)
		sender.setStringValue_(reporter._format_axis_value(index, value))

	def opacityChanged_(self, sender):
		reporter = _reporter_instance()
		if reporter is None:
			return
		reporter._opacity = float(sender.doubleValue())
		Glyphs.defaults[_OPACITY_DEFAULT_KEY] = reporter._opacity
		Glyphs.redraw()

	def colorChanged_(self, sender):
		reporter = _reporter_instance()
		if reporter is None:
			return
		reporter._overlay_color = sender.color()
		try:
			color = reporter._overlay_color.colorUsingColorSpaceName_(
				"NSCalibratedRGBColorSpace"
			)
			red, green, blue, alpha = (
				color.getRed_green_blue_alpha_(None, None, None, None)
			)
			Glyphs.defaults[_COLOR_DEFAULT_KEY] = [
				float(red), float(green), float(blue), float(alpha)
			]
		except Exception:
			reporter._report_error("Could not save overlay color")
		Glyphs.redraw()

	def resetAxes_(self, sender):
		reporter = self._reporter_for_palette()
		if reporter is None:
			return
		reporter._reset_axes_for_font(self._font_for_palette())
		self._sync_controls(reporter)

	@objc.python_method
	def __file__(self):
		return __file__
