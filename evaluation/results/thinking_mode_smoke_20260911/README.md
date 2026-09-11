# Thinking Mode Smoke Test

Date: 2026-09-11

This is an exploratory A/B test. It is intentionally kept separate from the
240-sample baseline and must not be combined with that report.

## Scope

- Model: `qwen3.7-plus`
- Input type: XLSX purchase orders
- Samples: 2 orders, 30 line items each
- Flow: document loading -> Qwen extraction -> FAISS matching -> risk control -> final business decision
- Thinking-on run: default model request configuration
- Thinking-off run: temporary `model_kwargs={"extra_body": {"enable_thinking": false}}` injection in the test process; repository code was not changed

## Results

| Order | Thinking | End-to-end latency | Success | Parsed items | Final decision |
|---|---:|---:|---:|---:|---|
| `mfg_auto_approve_0009.xlsx` | on | 88.4 s | yes | 30 | manual confirmation |
| `mfg_auto_approve_0009.xlsx` | off | 46.3 s | yes | 30 | manual confirmation |
| `mfg_manual_review_0009.xlsx` | on | 92.7 s | yes | 30 | manual confirmation |
| `mfg_manual_review_0009.xlsx` | off | 46.4 s | yes | 30 | manual confirmation |

Observed end-to-end latency reduction with thinking disabled: approximately
47%-50% for these two samples. The final business decision was unchanged.

## Limitations

This is not a quality benchmark. It has only two XLSX samples and does not
establish that disabling thinking preserves extraction accuracy across the
whole dataset.

During the first thinking-off attempt, the model returned visible reasoning
text around the JSON and the output parser failed; a retry then succeeded.
The DashScope/LangChain parameter mapping therefore needs to be verified before
changing production configuration.

Recommended next step: run a larger fixed A/B sample and compare field-level
accuracy, SKU accuracy, retry count, latency, and final business actions before
making the mode change permanent.
