<!-- SPDX-License-Identifier: CC-BY-4.0 -->
# Converters

Two converters let a repository that keeps requirements in Doorstop or StrictDoc switch to OSTF without retyping them. They need only Python 3.12 and PyYAML, which the [reader's environment](../conformance/README.md) already has. [check_tools.py](check_tools.py) runs both on the [samples](samples/) in CI: the Doorstop sample was written and validated with Doorstop 3.2, the StrictDoc sample with StrictDoc 0.30.4.

## Doorstop, both ways

```sh
python3 doorstop.py import DOORSTOP_DIR OSTF_DIR --type SYS=need --type TST=verification
python3 doorstop.py export OSTF_DIR DOORSTOP_DIR
```

`import` writes `trace.yaml` and one item file per Doorstop document under `doorstop/`. Each item keeps its UID as its ID. `--type PREFIX=TYPE` gives a document's items an OSTF type, `requirement` by default. `export` rebuilds the Doorstop tree from those files, including items added in OSTF; the sample comes back with every file equal to the original, and Doorstop validates the result.

| Doorstop | OSTF | On the way back |
| --- | --- | --- |
| UID | `id` | kept |
| `header` | `title` | kept |
| `text` | `text` | kept |
| `links` to parent items | `refines`, or `verifies` from a `verification` item | kept |
| link review stamps | `x-doorstop.link-stamps` | kept, never checked: in OSTF the pull request rechecks a link |
| `reviewed` | `x-doorstop.reviewed` | kept, never checked |
| `references` of type file | whole-file `code` anchors, or `tests` for a `verification` item, and `x-doorstop.references` | kept; a `keyword` is kept only in `x-doorstop` |
| `active: false` | `status: obsolete` | kept |
| `level`, `derived`, `normative`, `ref` | `x-doorstop` | kept |
| custom attributes | `attributes` when OSTF can hold the value, otherwise `x-doorstop.attributes` | kept |
| document settings | `x-doorstop` of the item file | kept |

What does not survive: Doorstop's review stamps carry no meaning in OSTF, so a link that Doorstop calls suspect is an ordinary link in OSTF, which the next pull request that touches its code shows beside its item. Going back, an anchor with a symbol keeps only its file; `status: draft` exports as active; and link attributes, `controls` links, other profile links, `aliases`, `section` and `rationale` have no Doorstop form; `export` names each one it drops.

## StrictDoc, into OSTF

```sh
python3 strictdoc.py import OSTF_DIR FILE.sdoc...
```

`import` writes one item file per document under `strictdoc/` and, when missing, a `trace.yaml` that includes them.

| StrictDoc | OSTF |
| --- | --- |
| `UID` | `id` |
| `TITLE`, `STATEMENT`, `RATIONALE` | `title`, `text`, `rationale` |
| `STATUS` Draft, Active, Deleted | `draft`, accepted, `obsolete` |
| `TAGS` | the list attribute `tags` |
| other fields | attributes, when the field name is a valid attribute name |
| Parent and Child relations, across all files imported together | `refines` |
| File relations, by `PATH` or the older `VALUE` | whole-file `code` anchors; a selector such as `FUNCTION` is reported and dropped |
| enclosing `[[SECTION]]` titles | `section`, joined by ` / ` |
| `COMMENT`, `LEVEL`, `MID`, relation roles | `x-strictdoc` |

What is lost: nodes without a UID, which have no stable identity, and `[TEXT]` nodes; custom grammars beyond their field values; and relation types other than Parent, Child and File. Each loss is printed. There is no export to StrictDoc.
