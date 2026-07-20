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

The canonical private source repository is not linked here intentionally.
