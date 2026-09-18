# Almor Proposal Builder — public deployment

This is the public Streamlit deployment wrapper for the private Almor Proposal
Builder source repository.

Customer proposal examples, handwritten signatures, Standard Terms, the Work
Authorization form, and the derived knowledge index are not committed in
plaintext. They are stored in `proposal_private_assets.enc` and require the
private `DATA_ENCRYPTION_KEY` configured in Streamlit Secrets.

The public website also requires `APP_ACCESS_CODE`, so only authorized users can
submit client material, consume the configured OpenAI API account, or generate
documents containing signatures.

The default AI routing uses `gpt-5.6-luna` for request and attachment extraction,
and `gpt-5.6-terra` for professional proposal drafting.

The cost editor opens with the standard 26-line ATS/Almor estimate. Every row is
editable, units can be selected as `hr`, `LS`, or `Ea`, Total is calculated from
`Est. × Rate`, and the supplied defaults total `$2,221.00`. Zero rows remain in
the editor and are omitted from the generated proposal.

The Scope tab accepts multiple borehole and test-pit quantity/depth groups.
Drilling and test pits may be used separately or together; retrieval and drafting
select drilling-only, test-pit-only, or mixed-investigation references and wording
without deriving quantities from contractor hours.

The **Generate a complete PDF from a Word proposal** workflow accepts a completed
Almor Word proposal and creates one PDF containing every proposal page, the
Standard Terms, and the original fillable Work Authorization form. Proposal facts
and the estimated cost are read from the uploaded Word file to fill the form. A
toggle controls whether handwritten signatures are added to the proposal signature
page; the Work Authorization form remains unsigned and fillable.

The **Add Final Proposal to Library** workflow writes reviewed Final Word files,
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


Generating a complete PDF automatically saves the uploaded original Word proposal and its
search index to the private library. No separate library action or AI draft is required.
If storage fails, the PDF remains downloadable and the app shows the failure; generate again
to retry. Repeated generation preserves existing review-learning records for the same file.

Every borehole proposal includes the approved 25 mm standpipe piezometer scope, with readings
at the end of drilling and one follow-up visit two weeks after the field program, regardless
of the groundwater-monitoring selection. The Word assembler ensures a missing clause is
added even if AI omits it. Uploaded borehole proposals missing the clause receive it in the
PDF and an updated Word download; the library retains the original uploaded Word. Existing
standpipe clauses and test-pit-only proposals are preserved.
