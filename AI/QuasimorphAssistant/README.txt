Quasimorph Assistant - Screen Watcher v1.6

Changes:
- Adds user-confirmed HUD knowledge: the large four-digit resource value is calories, not health.
- Adds user-confirmed mapping: the separate selected-mercenary health indicator (shown as 110 in the user's UI) is HP, not ammunition or AP.
- Requests Qwen to report calories and selected mercenary HP separately.
- Keeps the stateless per-frame analysis approach; only stable, user-confirmed HUD facts are included in the prompt.
- Keeps screen capture local through Ollama; no screenshots are saved by the script.

Install:
1. Stop the running watcher with Ctrl+C.
2. Extract the archive into D:\AI\QuasimorphAssistant and replace app\screen_watcher.py and start_watcher.bat.
3. Keep the existing .venv folder and all installed packages.
4. Run start_watcher.bat.

The knowledge file knowledge\hud_knowledge.json is an editable human-readable record of user-confirmed HUD mappings. The prompt currently contains the same facts directly.
