# Official case and acceptance map

Official task: [Organizational Structure and Functions Analysis](https://docs.google.com/document/d/1m-r31DH6Q__9OcN4WiP453CE6drlTTQ8Px3xi3IiVHk/edit). The two comparison documents provided so far are [edition No. 8, 25 June 2021](https://docs.google.com/document/d/1X2tNOF9_ZF2ms0Fnx1mWrUaAoMLHabTu/edit) and [edition No. 9, 23 December 2022](https://docs.google.com/document/d/1FUh7Ld40xk-gwXMdj5-_3-p-cYeIl2hu/edit) of the internal audit regulation. Treat No. 8 as **before** and No. 9 as **after**. Do not commit raw copies without checking their sharing rights.

The shared No. 9 file is exposed as plain text by Google Drive, while No. 8 is a DOCX. Support `.txt` in the prototype for this supplied pair in addition to the Word/PDF/Excel formats named in the case.

The case document itself does not name a track number. The team must verify in the event platform that this case belongs to its selected track and can be submitted by this repository.

| Must have from section 7 | Evidence in the demo |
|---|---|
| Identify reorganized, retained, and created units from annexes | Table of units with before/after names, change status, and source clauses |
| Compare functions and find possible losses | Function mapping with before owner, after owner or “not found,” and supporting excerpts |
| Compare units for possible duplication and conflict of interest | Separate potential findings with affected units, explanation, and supporting excerpts |
| Cite every finding | Document identity plus exact clause/paragraph or PDF page/Excel sheet and excerpt; open it from the UI |
| Produce a clear analytical conclusion | Short report with findings, uncertainty, and required human review |

The case also requires a working prototype, document-upload/results interface, source repository, README with launch instructions, and a short architecture description. Inputs may be Word, PDF, and Excel. The organizers say they provide a test set; use it for final validation when available. A checker may deliberately include a lost function and a duplication. Do not claim those are present in the two linked editions until verified.

## Grounded examples from the linked editions

- Clause 3.4: edition No. 9 lists IT audit/data analysis (ДИТААД) and operational audit (ДОА), while both editions list continuous monitoring (ДНМ) and audit quality/methodology (ДККМ). This supports a visible structure change and retained units.
- Clause 3.5 and following: reporting lines and staff composition change. Compare units and functions rather than matching clause numbers alone.
- The monitoring of corrective actions appears at No. 8 clause 5.8.7 and No. 9 clause 5.7.7. This is a useful *retained function despite renumbering* check, not a loss.

Potential conflict of interest is a review flag, not a legal or HR determination. The internal audit regulation discusses functional independence and administrative reporting; these facts alone do not prove a conflict.

## Scope for five hours

Implement the five must-haves and reproducible documentation first. External law/standards comparison, benchmarking against other operators, and redistribution recommendations are optional section 8 items. Do them only if the mandatory flow is stable and the relevant reference documents are supplied.

Judging weights: task/functionality 25, technical implementation 25, README/reproducibility 25, value 15, originality/development potential 10. A runnable, cited, understandable path earns attention across the first three criteria.
