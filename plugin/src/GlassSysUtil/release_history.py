"""Read offline notes for the installed release without fetching a newer feed."""
import json
import textwrap
from pathlib import Path


def load_notes(path, version, language):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("version") != version:
            return ""
        notes = document.get("notes", {})
        if not isinstance(notes, dict):
            return ""
        code = str(language).replace("-", "_").split("_")[0].lower()
        entries = document.get('entries')
        if isinstance(entries, list):
            blocks = []
            for entry in entries[:4]:
                if not isinstance(entry, dict) or not isinstance(entry.get('version'), str):
                    continue
                translated = entry.get('notes', {})
                if not isinstance(translated, dict):
                    continue
                text = translated.get(code) or translated.get('en', '')
                if isinstance(text, str) and text.strip():
                    lines = textwrap.wrap(' '.join(text.split()), 72)
                    if len(lines) > 3:
                        lines = lines[:3]
                        lines[-1] = lines[-1][:71] + '…'
                    date = entry.get('date', '')
                    heading = 'GSU ' + entry['version'] + (' — ' + date if isinstance(date, str) and date else '')
                    blocks.append(heading + '\n' + '\n'.join(lines))
            if blocks:
                return '\n\n────────────────────────\n\n'.join(blocks)
        value = notes.get(code) or notes.get("en", "")
        return value.strip() if isinstance(value, str) else ""
    except (OSError, ValueError, UnicodeError):
        return ""
