!macro customUnInstall
  MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON1 "Removing MemWeave will also remove all local memories, attachments, generated audio, logs, and local settings in $LOCALAPPDATA\MemWeave. Continue?" /SD IDYES IDYES +2
  Abort
  RMDir /r "$LOCALAPPDATA\MemWeave"
!macroend
