# Variable Font Overlay

Variable Font Overlay is a plugin for [Glyphs 3](https://glyphsapp.com/) that lets you preview any position in a variable-font designspace directly in Edit View.

Use the sliders in the Palette to explore your font’s axes. The interpolated result appears as a colored, translucent overlay, so you can compare it with the glyphs you are editing without switching masters or creating temporary instances.

## What you can do

- Preview arbitrary combinations of all variable axes in the current font.
- Adjust axis values with sliders or enter exact values directly.
- Compare an interpolation with the current master in Edit View.
- Preview paths, components, open paths, and surrounding glyphs.
- Change the overlay color and opacity.
- Reset every axis to the current master with one click.
- Toggle the overlay from the Palette, the View menu, or a keyboard shortcut.

The plugin chooses practical increments for common axes. Weight, width, optical size, italic, and grade use whole-number steps; slant uses tenths. Custom axes receive an increment appropriate for their range.

## Requirements

- Glyphs 3.2 or later
- A font with at least one variable axis and compatible masters

## Installation

1. Download the latest ZIP from [Releases](https://github.com/alikia2x/variable-font-overlay/releases/latest).
2. Unzip the download.
3. Double-click `Variable Font Overlay.glyphsPlugin` and confirm the installation in Glyphs.
4. Restart Glyphs.

When upgrading from an older version named **Variable Font Overlay Preview**, remove the old plugin before installing the new one. You can manage installed plugins in `Window → Plugin Manager`.

## Usage

1. Open a variable font project and enter Edit View.
2. Choose `Window → Palette` if the Palette is not already visible.
3. Expand **Variable Font Overlay**.
4. Enable **Show overlay**.
5. Move an axis slider or enter a value in its number field.

The overlay follows the axis values immediately. Its color and opacity are shown at the bottom of the Palette and are remembered after you restart Glyphs.

Choose **Reset to Current Master** to return all sliders to the location of the master you are editing.

## Menu and keyboard shortcut

You can also toggle the preview from:

`View → Variable Font Overlay`

The default shortcut is:

`Control–Option–V`

## Troubleshooting

### The Palette is not visible

Choose `Window → Palette`, then look for **Variable Font Overlay** in the right sidebar.

### No axis controls appear

Make sure the current font has axes configured in `File → Font Info → Font → Axes` and that its masters have axis values.

### The plugin does not appear after installation

Restart Glyphs completely. If macOS blocks the plugin, right-click it in Finder, choose **Open**, and confirm the prompt.

### An older installation conflicts with this version

Quit Glyphs and remove any old `Variable Font Overlay Preview.glyphsReporter` or `Variable Font Overlay Preview.glyphsPlugin` from:

`~/Library/Application Support/Glyphs 3/Plugins/`

Then install the current plugin and restart Glyphs.

## License

Copyright 2026 alikia2x.

Licensed under the [Apache License 2.0](LICENSE).
