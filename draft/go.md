<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Go language annex: go1

Document revision 0.5, wire version 0.2, 2026-10-19. Draft annex for OSTF-011 and OSTF-014. References: the [Go specification, lexical elements](https://go.dev/ref/spec#Lexical_elements), [function declarations](https://go.dev/ref/spec#Function_declarations) and [declarations](https://go.dev/ref/spec#Declarations_and_scope). These links define language syntax; the rules below define the trace projection.

## Symbol binding

- A package-level function is `Name`. A method is `Receiver.Name`. Strip receiver pointer indirection and generic type arguments when forming Receiver. Do not include the receiver parameter variable.
- A top-level type, variable or constant is its declared name. A multi-name value specification gives each name the same span. Import declarations are not anchors.
- First match the full symbol. If no exact match exists and the query contains no dot, match the last component of method names. If several declarations match, preserve source order and concatenate their token streams with one ASCII space before hashing.
- For a function/method, the definition begins at `func` and ends immediately after the closing body brace, or after the declaration header for a bodyless function. Its sig ends immediately before the opening body brace; its body covers the whole definition. Braces in parameter/result types are part of the header.
- For an ungrouped type/var/const, include the declaration keyword and whole declaration. For a grouped declaration, include only the individual specification, without the enclosing keyword/parentheses. Sig and body are identical for these declarations. Do not include trailing comments or an explicit declaration terminator outside the specification span.
- A definition's tag-binding range includes the directly attached Go doc-comment group and its own declaration. Other comments bind only when inside a definition. A tag in a string literal is not a tag. A whole-file tag can appear in any comment.

## Token bytes

Split the selected span using Go's lexical token rules. Drop comments, whitespace and automatically inserted end-of-line semicolons. Keep explicit `;` tokens. Keep identifiers and literal spelling, including numeric base/underscores and escape sequences. A raw string literal drops CR bytes as Go's scanner does; other literal spelling is unchanged. Do not fold Unicode or normalize escapes. Join token spellings with exactly one ASCII space, without leading/trailing space. SHA-256 and unpadded base64url yield `go1:<digest>`.

A whole Go file uses the same tokens for sig and omits body. Code that cannot be parsed uses the whole-file `lf1` fallback rather than a fabricated token-bound symbol; the tool must disclose reduced precision. `lf1` is not an alternative valid Go token algorithm.

## Executable boundary

[code-vectors.json](../conformance/code-vectors.json) includes literal token bytes and fixed hashes for whole files, ordinary functions, pointer/generic methods (including two receiver type arguments), interface/function literal types in signatures, grouped and ungrouped declarations, multi-name values, explicit semicolons, multiline block comments, Unicode, raw strings and formatting changes. [Repository cases](../conformance/repositories.json) exercise anchors, tags, alias resolution and states.

The Python prototype uses tree-sitter Go rather than Go's parser/scanner. Its supported syntax and any rejected constructs must be reported in its README and results. Passing these vectors is evidence for this draft subset, not an exhaustive Go grammar or full Core claim.
