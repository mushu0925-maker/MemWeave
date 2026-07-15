# Storage Adapters

Storage adapters hide persistence details from the domains. The current JSON store and optional SQLite document backend should expose the same store behavior; domain rules must not depend on which one is active.

中文：存储适配层用来隔离 JSON、SQLite 等底层差异。Domain 只依赖统一的 store 行为，不应关心当前存储实现。
