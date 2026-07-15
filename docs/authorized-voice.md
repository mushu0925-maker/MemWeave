# Authorized Voice Output

Voice output is optional and separate from memory extraction.

MemWeave first decides a fixed assistant `reply_text` using allowed evidence. Only then may an external IndexTTS2 adapter read that text. The voice adapter cannot decide facts, rewrite the reply, or bypass runtime evidence guards.

Generation requires:

- an active profile;
- an authorized audio/video reference saved as a raw source;
- explicit reference consent;
- confirmed target-person segment attribution;
- explicit consent for each generation request;
- an available external adapter and output directory.

Generated audio is marked as AI generated. Revoking or deleting a voice reference blocks future generation and removes derived generation records according to the active workflow.

Do not commit voice references, extracted audio, generated audio, model weights, or consent records to the source repository.
