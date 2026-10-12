# Draft: request to PSX Market Data for KSE-100 index history

**Status:** draft, not sent. The team sends it from a team member's university email.
**To:** marketdatarequest@psx.com.pk (the contact PSX's website gives for data licences and
permission to use market data)
**Why it is needed:** the backtest compares a portfolio with the KSE-100 (PRD.md FR32). No
source we found may be used without PSX's permission: the PSX website's terms forbid automated
retrieval and storing index levels, and Yahoo Finance has no KSE-100 series (Memory.md §4).
Until PSX replies, the report uses a stand-in benchmark that is never called KSE-100.

---

**Subject:** Permission request: daily KSE-100 and KSE100PR closes for a university final-year project

Dear Market Data Team,

We are final-year Computer Science students at [university name]. Our final-year project,
InvestIQ, is an advisory tool for retail investors on the Pakistan Stock Exchange. It does not
place trades. One of its features tests a suggested portfolio on past prices and compares the
result with the KSE-100.

We would like to ask for written permission to use the following data for this project:

- Daily closing values of the **KSE-100 Index (KSE100)** and the **KSE-100 Price Return Index
  (KSE100PR)**
- From **1 October 2021** to the present date
- If possible, as a single file (CSV or Excel) with the date and closing value

How we would use it:

- For academic, non-commercial use only, as part of our final-year project and its evaluation
  by our department
- Stored privately in the project's database and not redistributed, sold or published as a
  dataset
- Shown only inside the application as a comparison line on a chart, with PSX named as the
  source
- The application is not publicly released; it is demonstrated to our supervisor and
  evaluation panel

We have not downloaded or stored this data from the PSX website, because your terms of use
do not allow it without permission. If a licence or a fee applies to this kind of use, we
would be grateful to know the terms.

Thank you for considering our request.

Yours sincerely,

[Name], [Roll number]
[Name], [Roll number]
Department of [department], [university name]
Supervisor: [name and email]

---

**After PSX replies**

- Save the reply (or its date and reference) in `docs/` and record it in Memory.md §4 and §9.
- Load the file with `python -m services.index_data load <file.csv> --spot-checks <published.csv>`
  after writing its manifest (`index_code`, `dataset_version`, `source` with the permission
  date, `sha256`). The loader refuses the file if a row is malformed or a spot check does not
  match, and writes its checks to `<file>.validation.json`.
- New backtests then show the KSE-100 next to the stand-in automatically; no code change.
