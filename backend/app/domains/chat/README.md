# Chat

The chat domain selects relevant persona-item slices, assembles runtime context, records conversations, and passes possible new evidence into the candidate-review flow.

It must not send the entire profile by default. `chat_records` are conversation history, not verified facts, and a claim discovered in chat cannot become a high-confidence persona item without confirmation.

中文：Chat 只取当前消息需要的记忆切片。聊天记录不等于事实，新信息必须先进入候选与确认流程。
