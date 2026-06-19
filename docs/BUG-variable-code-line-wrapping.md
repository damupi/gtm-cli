# BUG — Custom JavaScript variable code is line-wrapped on write

## Summary

When the GTM CLI updates a Custom JavaScript variable via the API, it mangles the code by splitting long lines at a fixed character width. The result is syntactically broken JavaScript that cannot execute correctly.

## Affected operation

`gtm variables update` (or any write path that serialises a variable's `parameter[type=template].value` containing multi-line JavaScript)

## Steps to reproduce

1. Have a Custom JavaScript variable in GTM with long lines (e.g. a line > ~80 chars)
2. Use the CLI to update the variable content
3. Open the variable in the GTM UI

## Observed behaviour

Lines are broken mid-expression at an apparent fixed character width. Examples from a real `CJS - IsBot` variable update:

```
// Safe
body access guard              ← comment split, "body access guard" becomes plain code
var body = document.body || document.documentElement;

var bwrSize = {
      width:  window.innerWidth  || (body &&
body.clientWidth)              ← object property split mid-expression
|| 0,
      height: window.innerHeight || (body &&
body.clientHeight) || 0

var userAgent
=                              ← assignment split across lines
navigator.userAgent.toLowerCase();
```

This produces a syntax error (`body access guard` is an identifier expression, not a comment) and breaks variable assignment (`var userAgent\n=\n...` is valid JS but `body access guard` is not).

## Expected behaviour

The variable code should be written back exactly as provided — no line wrapping, no reformatting.

## Root cause

**Shell quoting, not Python serialisation.** When multi-line JS is passed via `--param javascript:<code>`, the shell corrupts long lines before the Python process ever receives them. The GTM API and Python serialisation layer are fine — the problem is at the shell boundary.

Passing large multi-line strings inline via `--param key:value` is inherently unsafe: the shell expands, splits, and re-quotes the argument in ways that break whitespace and line continuations. The fix is to never pass JS code inline — always read it from a file.

## Impact

- Any Custom JavaScript or Custom HTML variable written via `--param javascript:<code>` inline will be corrupted if the code contains long lines or complex whitespace
- Silent failure — the CLI reports success, but the code in GTM is broken
- The variable may still "save" in GTM but will throw a runtime syntax error on every pageview

## Workaround

Use `--param-file javascript:/path/to/code.js` to pass the code from a file, bypassing the shell quoting problem entirely. The GTM API handles the content correctly once it reaches Python.

## Fix suggestions

1. Read the input JavaScript as a raw string and pass it verbatim as the `value` field — no wrapping, no formatting
2. Add an integration test: write a variable with a line > 100 chars, read it back, assert the content is byte-for-byte identical
3. Consider adding a `--param-file key:path` flag that reads the JS from a file and sends it as-is, bypassing any string processing

## Important: GTM variable syntax in JS code

Custom JavaScript variables often reference other GTM variables using double curly bracket syntax: `{{variableName}}`. For example:

```js
var myVar = {{Page URL}};
```

The `--param-file` flag must pass these through verbatim — double curly brackets must **not** be escaped, replaced, or interpreted before being sent to the API.

## Related

- PRD Phase 2 (add write operations) — this bug will affect all write operations that handle JavaScript/HTML content
- Affected variables: `CJS - IsBot` (GTM-TJ32CD6), likely any Custom JavaScript or Custom HTML variable
