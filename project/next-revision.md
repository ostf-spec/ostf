<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Questions for the next text of the draft

Gaps found in working draft 0.3 of 2026-10-26 that no change settled yet. Each is settled in the text with a case, under a new identifier where a rule changes.

- **The subject of a diagnostic on a defined root key's value, or on a whole file.** No rule of Annex D.2 applies to a defect in the value of `tags`, `include`, `items`, `sources` as a whole or `profile`, to `INCLUDE_EMPTY`, or to a failure of a whole file such as its version. The reference reader gives the key, the glob or the profile's path, or no subject, and no case compares them; found while settling the subjects of source entries and profile keys.
- **Values that Annex G writes unescaped on one line.** Rule 5 writes a link attribute as `name=value` and rule 2 an external item's `revision` as it is, and either value may hold a line break, which splits the line, as a view did before rule 5 wrote it as Annex E.2 writes a value. Found while fixing the rendering of a view; no case pins either.
- **How a text under one date is identified.** The draft's header date, 2026-10-26, did not change while OSTF-114, Annex D.2, Annex E.3 and Annex G changed under it, and an external item that copies a requirement cites that date as its `revision` (OSTF-113), so a refreshed copy cannot be told from the old one by its revision; zztrace's items for OSTF-114, Annex D.2 and Annex G show it. The spec session rules on how a text under one date is identified.
