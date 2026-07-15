# classification

Owns AI input dissection and A-M library classification.

中文备注：

```text
classification 只负责把 raw_source 内容分类成候选 persona item 结果和 diagnostics。
不能生成本地保底 persona_items。
覆盖不足进入 coverage_warnings / uncertainty seeds，不应直接变成 fatal error。
```
