# Floating Desktop Timer & Stopwatch

A Python/PySide6 floating timer for Windows 10 and Windows 11. It features a transparent, frameless, always-on-top display, right-click controls, and Windows global hotkeys.

## Features

- Stopwatch and countdown modes with `DD:HH:MM:SS` display.
- Monotonic-clock timekeeping; display updates do not rely on tick counts.
- Pause/resume functionality.
- Stopwatch and countdown values are retained separately when switching modes.
- Right-click context menu with no permanently visible control panel.
- Drag the display to reposition the window.
- Resize the window from any edge or corner.
- Always-on-top, frameless window with a transparent background by default.
- Customizable font color, background color, and background opacity.
- Global keyboard shortcuts using the Windows `RegisterHotKey` API.
- Persistent settings using Qt's `QSettings`, including window geometry, mode, shortcuts, colors, opacity, and countdown duration.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or newer (64-bit recommended)
- PySide6

## Download and Extract Dependencies

1. Open the GitHub repository.
2. Download the repository as a ZIP file using **Code → Download ZIP**.
3. Extract the downloaded ZIP file to your preferred location.
4. Locate the project folder and its included `dependencies` folder.

Make sure the `dependencies` folder remains in the expected project directory.

## Dependencies and miscellaneous.md are regularly being and developed and updated

Check for updates. 

## Installation

Open Command Prompt or PowerShell inside the project folder.

Create a virtual environment:

```powershell
py -m venv .venv
```

Activate the virtual environment:

```powershell
.venv\Scripts\activate
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install the required packages using the included dependency files:

```powershell
pip install -r requirements.txt
```

## Run

Start the application:

```powershell
python app.py
```

## Usage

- **Drag:** Left-click and drag the timer body to reposition it.
- **Resize:** Drag any edge or corner of the window.
- **Controls:** Right-click anywhere on the timer.
- **Start / Stop:** Use the context menu or global toggle shortcut.
- **Reset:** Use the context menu or reset shortcut.
- **Modes:** Select Elapsed Time Mode or Countdown Timer Mode from the context menu.
- **Countdown:** Use Configure Countdown to set days, hours, minutes, and seconds.
- **Appearance:** Customize font color, background color, and opacity from the context menu.
- **Hotkeys:** Use Set Hotkeys to customize global keyboard shortcuts.

### Default Global Shortcuts

| Shortcut | Action |
|---|---|
| `Alt+5` | Start / Stop toggle |
| `Alt+6` | Reset |

Global shortcuts are registered through Windows and work even when another application is active.

If a shortcut is already registered by another application, open **Set Hotkeys** and choose a different combination.

The shortcut editor supports one or more modifiers plus one letter, digit, Space, Tab, Enter, Esc, or F1–F12 key.

## Behavior Notes

- Stopwatch and countdown values are stored separately.
- Switching modes pauses the currently active mode while preserving its value.
- Selecting countdown mode opens the duration editor.
- The configured countdown duration is restored on subsequent launches.
- Reset in stopwatch mode returns the timer to zero.
- Reset in countdown mode restores the configured countdown duration.
- A countdown stops at zero and never displays a negative value.
- Background opacity is independent of the selected background color:
  - `0` = Fully transparent
  - `255` = Fully opaque
- The default background opacity is `0`.
- Settings are stored through Windows Qt `QSettings`, not in a project-local configuration file.

## Project Structure

```text
floating_desktop_timer/
├── app.py
├── requirements.txt
├── README.md
└── dependencies/
    └── (included dependency files)
```

## Troubleshooting

**A global shortcut does not work**

Another application may already be using the selected shortcut. Open the context menu, select **Set Hotkeys**, and choose another combination.

**The display is hard to see**

Change the font color. If you want a visible panel behind the timer, select a background color and increase Background Opacity.

**Python cannot import PySide6**

Make sure your virtual environment is activated and run:

```powershell
pip install -r requirements.txt
```

**Installation fails**

Verify that you extracted the complete repository ZIP, including the `dependencies` folder, and that you are running the installation commands from the correct project directory.

## Project Limitations

This project is source-code-only.

- Does not use PyInstaller.
- Does not generate an executable.
- Does not provide taskbar integration.
- Does not create a system-tray timer.

Python and the required dependencies must be installed to run the application.
