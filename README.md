# Terminal Rogue

Terminal Rogue is a Python cyber-ops roguelike with a custom PySide6 desktop UI, turn-based encounters, evolving node maps, contracts, and a staged tutorial flow.

## Run From Source

1. Create and activate a Python virtual environment.
2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Launch the game:

```powershell
python main.py
```

## Build A Windows Executable

This repo includes a PyInstaller build script and spec file.

```powershell
.\build_exe.ps1 -Clean
```

Built output:

- `dist\TerminalRogue\TerminalRogue.exe`

## Notes

- Runtime YAML data is bundled into the packaged app.
- Save data is stored in the user's local app-data folder.
