# Classification

This domain turns raw-source content into candidate A-M persona items and diagnostics.

It does not write invented local fallback persona items when the model fails. Missing coverage becomes `coverage_warnings` or uncertainty seeds so that the user can review the gap without losing the raw source.

中文：Classification 只负责从 raw source 产生候选条目和诊断。分类失败不能伪造保底 persona item；覆盖不足应进入待确认流程。
