# BUG — `variable get --format json` emits invalid JSON for jsm variables

## Status

Fixed — `output()` now uses `print()` instead of `console.print()` for JSON and YAML formats, bypassing Rich's markup engine entirely.

## Symptom

`gtm variable get -f json` produces malformed JSON when the variable is a Custom JavaScript (`jsm`) type. The JS function body is embedded with **literal newlines** instead of escaped `\n` sequences, making the output unparseable.

```bash
gtm -a 3116374124 -c 9253028 -w 472 -f json variable get 495 | jq .
# jq: parse error: Invalid string: control characters from U+0000 through U+001F
# must be escaped at line 21, column 79

gtm -a 3116374124 -c 9253028 -w 472 -f json variable get 495 | python3 -c \
  "import json,sys; json.load(sys.stdin)"
# json.decoder.JSONDecodeError: Invalid control character at: line 9 column 81
```

Same issue applies to `tag get -f json` for Custom HTML tags.

## Root cause

The JSON output formatter does not escape control characters (newlines, tabs) inside string values before serializing. The GTM API returns the JS/HTML body as a properly escaped JSON string — the bug is in the CLI's output layer, which writes the unescaped string directly.

## Impact

- Agents and scripts cannot reliably parse `variable get` output for jsm/html variables
- Forces fallback to Python regex / string splitting workarounds
- Breaks any pipeline using `jq` to extract JS/HTML content

## Affected commands

- `gtm variable get -f json` — jsm type variables
- `gtm tag get -f json` — Custom HTML tags
- Likely any `*get -f json` where a parameter value contains multi-line text

## Fix

In the output formatter, ensure JS/HTML string values are properly escaped before JSON serialization. In Python:

```python
import json
# Use json.dumps() which correctly escapes control characters
output = json.dumps(data, ensure_ascii=False, indent=2)
```

If the formatter is writing raw strings bypassing `json.dumps`, switch to proper serialization.

## Workaround (for agents)

Do not attempt to parse `variable get -f json` for jsm variables. Instead:

1. **Write the full function body from scratch** rather than read-modify-write. Read the existing variable body visually (table output) and construct the complete new version.
2. **Use table/plain output** for inspection: `gtm variable get 495` (no `-f json`) returns a tab-separated format that is safe to read line by line.

## Note on GTM variable references in JavaScript

GTM variable references inside JS/HTML use double curly bracket syntax: `{{variableName}}`. These are resolved by GTM at runtime and must be passed through verbatim — never escape or modify them. Example:

```javascript
function() {
  var deviceType = {{CJS - deviceType}};
  var containerId = {{Container ID}};
  return deviceType === 'm';
}
```

When writing variable bodies to a temp file for `--param-file`, ensure `{{...}}` references are preserved exactly as-is.

## Related

- `BUG-variable-code-line-wrapping.md` — related output formatting issue
- `docs/AI-USAGE.md` — agent workaround documented
