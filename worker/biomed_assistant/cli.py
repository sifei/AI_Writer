import json
import sys

from analyzer import analyze_submission
from converter import convert_docx_to_journal_format
from extractor import extract_uploaded_text


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        command = payload.get("command", "analyze")
        if command == "convert_docx":
            result = convert_docx_to_journal_format(payload)
        elif command == "extract_upload":
            result = extract_uploaded_text(payload)
        else:
            result = analyze_submission(payload)
        sys.stdout.write(json.dumps(result))
        return 0
    except Exception as exc:  # pragma: no cover - surfaced to Next API route.
        sys.stderr.write(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
