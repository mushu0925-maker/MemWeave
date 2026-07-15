# Authorized Voice Output

Voice output is optional. It runs after the chat reply has been decided and does not take part in memory extraction or fact selection.

MemWeave first creates a fixed `reply_text` from evidence that is allowed at runtime. An external IndexTTS2 adapter may then read that text aloud. The adapter cannot choose facts, rewrite the reply, or bypass the evidence guards.

A generation request is accepted only when all of the following are available:

- an active profile;
- an authorized audio/video reference saved as a raw source;
- explicit reference consent;
- confirmed target-person segment attribution;
- explicit consent for each generation request;
- an available external adapter and output directory.

Generated audio is marked as AI generated. Revoking or deleting a voice reference blocks later generation and removes derived generation records according to the active workflow.

Voice references, extracted audio, generated audio, model weights, and consent records do not belong in the source repository.
