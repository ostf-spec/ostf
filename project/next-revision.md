<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Questions for the next text of the draft

Gaps found in working draft 0.3 of 2026-10-26 that no change settled yet. Each is settled in the text with a case, under a new identifier where a rule changes.

- **Attribute value types.** OSTF-114 lets a profile declare an attribute's value type but names no value types; the profile schema accepts `string`, `text`, `number`, `boolean` and `list`, and the text says neither which values each accepts nor how `text` and `string` differ.
- **The subject of a tag's diagnostic.** Annex D.2 makes the line of a tag a subject without saying whether the line includes its comment marker: the reference reader gives `@req R-A`, zztrace's reader `// @req R-A`.
- **The subject of a diagnostic on a source entry or a profile key.** No rule of Annex D.2 applies, and the two readers give different subjects.
