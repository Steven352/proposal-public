# Almor Proposal Builder — public deployment

This is the public Streamlit deployment wrapper for the private Almor Proposal
Builder source repository.

Customer proposal examples, handwritten signatures, Standard Terms, the Work
Authorization form, and the derived knowledge index are not committed in
plaintext. They are stored in `proposal_private_assets.enc` and require the
private `DATA_ENCRYPTION_KEY` configured in Streamlit Secrets.

The public website requires an access code to submit client material and use the
proposal builder.

Step 1 accepts Outlook `.msg` and `.eml` emails (including supported attachments),
Word (`.doc`, `.docx`, `.docm`, `.odt`, `.rtf`), PDF, Excel (`.xls`, `.xlsx`,
`.xlsm`, `.xlsb`, `.ods`), CSV/TSV, PowerPoint, common images, and text/HTML.
Legacy Office files are converted with LibreOffice before analysis. PDFs and
images also reach the vision model, including scanned pages. Each file must be
20 MB or smaller. Damaged or password-protected files produce a named error;
unsupported email attachments are identified as not analyzed in the extraction input.

The default AI routing uses `gpt-5.6-luna` for request and attachment extraction,
and `gpt-5.6-terra` for professional proposal drafting.

The cost editor opens with the standard 26-line ATS/Almor estimate. Every row is
editable, units can be selected as `hr`, `LS`, or `Ea`, and Total is calculated from
`Est. × Rate`. Quantities start at zero. Zero rows remain in the editor and are
omitted from the generated proposal.

The Scope tab accepts multiple borehole and test-pit quantity/depth groups.
Drilling and test pits may be used separately or together; retrieval and drafting
select drilling-only, test-pit-only, or mixed-investigation references and wording
without deriving quantities from contractor hours.

Every generated Word proposal uses the same standard Almor layout, based on the
supplied P026-168 902 to 916 67 Ave S.W. reference and packaged as
`data/templates/standard_proposal.docx`. Historical matches provide writing
examples only. They do not select page layout, headers, styles, standard
sections, or the cost table. The cost table uses one fixed six-column format with
8-point Arial text, consistent widths and alternating shading. Repeating headers
are populated directly from the current client, project, location and proposal
number; first-page company letterhead is retained.

Enter the proposal number once in Step 1. That value is used in the proposal,
every project header and the download filename. Changing it removes the previous
download so the document can be regenerated with the new number.

After the proposal editor opens, **Download draft** saves a portable JSON
checkpoint containing the current facts, scope edits, cost edits, request text,
notes, and personnel option. Use **Save or restore draft → Upload an Almor draft
→ Restore draft** in a later session to continue. Original uploaded source files
are intentionally not embedded; upload them again only when re-running extraction.

Immediately above **Generate Word proposal**, **Include Proposed Project Personnel
section** is checked by default. Uncheck it to omit the complete personnel section.
When the selected layout has no personnel section, the checked option imports that
section from an existing historical template while retaining the selected layout.

Word's **Hide White Space** view hides headers and footers on screen. Double-click
the boundary between pages to restore them; this does not change the document.

The **Generate a complete PDF from a Word proposal** workflow accepts a completed
Almor Word proposal and creates one PDF containing every proposal page, the
Standard Terms, and the original fillable Work Authorization form. Proposal facts
and the estimated cost are read from the uploaded Word file to fill the form.
Signing access shows a toggle for adding handwritten signatures to the proposal
signature page. The Work Authorization form remains unsigned and fillable.

Signing access also enables **Add Final Proposal to Library**, which writes reviewed Final Word files,
their search records, and private draft/final revision records directly to the
private source repository. Reusable edits must occur in at least three reviewed
proposals and still require explicit approval before becoming drafting rules.
This workflow requires these additional Streamlit Secrets:

```toml
GITHUB_LIBRARY_TOKEN = "a-fine-grained-token-restricted-to-Steven352/proposal"
GITHUB_LIBRARY_REPO = "Steven352/proposal"
GITHUB_LIBRARY_BRANCH = "main"
```

The fine-grained token must have **Contents: Read and write** permission only on
the private proposal repository. It must never be committed to this public
deployment repository.

The canonical private source repository is not linked here intentionally.


With signing access, generating a complete PDF automatically saves the uploaded original Word
proposal and its search index to the private library. If storage fails, the PDF remains available
and the app reports the error. Generate again to retry. Repeated generation preserves existing
review-learning records for the same file. Standard access generates an unsigned PDF and client
email draft for the current session.

The generated scope uses the approved nine bullets and closing paragraph verbatim, with only
investigation quantities, depths, and necessary method-specific substitutions. AI output, historical
examples, notes and cost rows cannot append or rewrite scope clauses. The laboratory bullet includes
the approved disturbed-sample and discretionary Shelby-tube wording. Test-pit-only programs omit
borehole-only SPT, Shelby-tube and standpipe wording. Users can edit or add clauses in the downloaded
Word. The reviewed Word is preserved when creating the final PDF, without restoring removed clauses.

Front matter uses one fixed letter layout: date/proposal number, client and multiline mailing address,
Attention with contact title and email, the fixed Re line, and the multiline site address. City and
province share a line; postal code is on its own line. Supplied legal descriptions are retained and
missing address details are never invented.
