# AI Model Cost Calculator Guide

The **🤖 AI Model Costs** tab in the **💰 Cost Tools** modal lets you estimate monthly Azure OpenAI token consumption costs before you write a single line of code. No Azure login is needed — everything runs in the browser.

> **Also see:** [🤖 Select Model](#-select-model-switching-your-projects-model) — the companion feature that **applies** your model choice to a generated project (local `.env` or a live Azure Container App).

---

## Overview

| Field | What to enter |
|---|---|
| **Model** | The Azure OpenAI deployment model you plan to use |
| **Monthly API Calls** | How many times your application will call the model per month |
| **Avg Input Tokens / Call** | Average number of tokens sent *to* the model per request (prompt + context) |
| **Avg Output Tokens / Call** | Average number of tokens returned *from* the model per request (completion) |

The calculator multiplies your usage by the current Azure OpenAI list prices and shows three live figures: **Input Cost / month**, **Output Cost / month**, and **Total Cost / month**.

---

## How to Use

1. Open any project card in the portal and click **💰 Cost Tools**.
2. Click the **🤖 AI Model Costs** tab (fourth tab, after What-If CLI).
3. Select a model from the dropdown — the per-million-token prices update instantly below the selector.
4. Enter your expected usage:
   - **Monthly API Calls** — e.g. `10000` for 10 thousand requests per month
   - **Avg Input Tokens / Call** — a typical GPT-4o prompt with context is 300–800 tokens
   - **Avg Output Tokens / Call** — a short answer is 100–300 tokens; a detailed response can be 500–2000
5. Read the cost summary at the top of the results panel.
6. Scroll down to the **Reference Prices** table to compare models side by side.

> **Tip:** Try different models to see how much you can save. Switching from GPT-4o to GPT-4o mini reduces costs by more than 90% for many chat workloads.

---

## Supported Models

| Model | Best For | Input $/1M tokens | Output $/1M tokens |
|---|---|---|---|
| **GPT-4o** | Multimodal reasoning, complex tasks | $2.50 | $10.00 |
| **GPT-4o mini** | High-volume chat, classification | $0.15 | $0.60 |
| **GPT-4.1** | Long-context reasoning (1M token window) | $2.00 | $8.00 |
| **GPT-4.1 mini** | Cost-efficient long-context tasks | $0.40 | $1.60 |
| **GPT-4.1 nano** | Ultra-low-cost summarization / triage | $0.10 | $0.40 |
| **o1** | Deep multi-step reasoning | $15.00 | $60.00 |
| **o1-mini** | Focused reasoning at lower cost | $1.10 | $4.40 |
| **o3-mini** | Fast reasoning, code generation | $1.10 | $4.40 |

Prices are in USD and represent Azure OpenAI pay-as-you-go list prices as of June 2025. Always verify current rates on the [Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/).

---

## Understanding Token Counts

**What is a token?**
Tokens are chunks of text — roughly 4 characters or ¾ of a word in English. The model processes and charges for tokens, not characters or words.

**Rule of thumb for estimation:**

| Content Type | Approx. Tokens |
|---|---|
| Short instruction prompt | 50–150 |
| Typical chat message with context | 300–800 |
| Full document page (RAG context) | 500–800 |
| Short answer / yes-no | 10–50 |
| Paragraph-length answer | 100–300 |
| Detailed explanation | 300–700 |
| Code snippet (function) | 150–400 |

**System prompt tip:** If your application uses a system prompt, add its token count to every input call. A 200-token system prompt on 10,000 calls/month adds 2 million input tokens.

---

## Example Estimates

### Customer support chatbot (GPT-4o mini)
- 50,000 calls/month
- 600 input tokens (user message + conversation history)
- 250 output tokens (agent reply)
- **Monthly estimate: ~$13.25**

### Technical document Q&A (GPT-4o)
- 5,000 calls/month
- 1,500 input tokens (document chunk + question)
- 400 output tokens (answer)
- **Monthly estimate: ~$38.75**

### Reasoning-heavy pipeline (o1)
- 500 calls/month
- 2,000 input tokens (problem description)
- 3,000 output tokens (step-by-step solution)
- **Monthly estimate: ~$105.00**

---

## Frequently Asked Questions

**Q: Why are these prices different from what I see in my Azure bill?**
The calculator uses Azure OpenAI list prices (pay-as-you-go). Your actual bill may be lower if you have provisioned throughput (PTU) reservations, enterprise agreements, or Azure credits.

**Q: What is the difference between pay-as-you-go and provisioned throughput (PTU)?**
Pay-as-you-go charges per token used — ideal for variable or unpredictable workloads. Provisioned throughput reserves a fixed number of tokens per minute and is more cost-efficient at high, steady volume. This calculator covers pay-as-you-go only.

**Q: Does the calculator include embedding models (e.g. text-embedding-3-small)?**
Not yet — the current version covers chat completion and reasoning models. Embedding costs are typically much lower (< $0.02 / 1M tokens) and can be added separately.

**Q: How do I estimate tokens without running the app?**
Use the [Azure OpenAI Tokenizer](https://platform.openai.com/tokenizer) to paste a sample prompt and see its exact token count. Then multiply by your expected call volume.

**Q: Will the prices go out of date?**
Yes. Microsoft periodically updates Azure OpenAI pricing. The guide and portal show the last-updated date. Always confirm on the [Azure OpenAI pricing page](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) before committing to a budget.

---

## Related Resources

- [Azure OpenAI Service pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Azure OpenAI Tokenizer](https://platform.openai.com/tokenizer)
- [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [💰 Cost Estimation Guide](COST_ESTIMATION_GUIDE.md) — infrastructure cost estimation (Bicep-based)
- [📡 Observability Guide](OBSERVABILITY_GUIDE.md) — post-deployment monitoring 

---

## 🤖 Select Model — Switching Your Project's Model

Once you've picked a model in the cost calculator, use **🤖 Select Model** to *apply* that choice to a generated project.

### In the Portal

Every project card has a **🤖 Select Model** button next to **🚀 Deploy**. It opens a modal with:

- **Model catalog** — 5 chat models (gpt-5.2, gpt-5.2-mini, gpt-4o, gpt-4o-mini, o4-mini) shown as radio cards with tier badge, input/output price per 1M tokens, strengths (+) and trade-offs (−)
- **Target toggle**:
  - **Local (.env)** — prints the command to run the project's `scripts/select_model.ps1`
  - **Azure Container App** — reveals Container App + Resource Group fields and generates a ready-to-copy `az containerapp update --set-env-vars` command

### Via CLI (inside the project folder)

Every project generated by the factory ships with `scripts/select_model.ps1`:

```powershell
# Local dev — updates .env
./scripts/select_model.ps1

# Apply to a deployed Container App
./scripts/select_model.ps1 -Target azure `
  -ContainerApp my-project-app `
  -ResourceGroup my-project-dev-rg

# Both
./scripts/select_model.ps1 -Target both `
  -ContainerApp my-project-app `
  -ResourceGroup my-project-dev-rg
```

The script displays the same interactive table as the portal and writes `AZURE_OPENAI_DEPLOYMENT=<model>` to the chosen target.

### Prerequisite

The selected deployment name must already exist in your Azure OpenAI resource. Create it via Azure AI Foundry portal or:

```bash
az cognitiveservices account deployment create \
  --name <aoai-resource> --resource-group <rg> \
  --deployment-name gpt-4o-mini \
  --model-name gpt-4o-mini \
  --model-format OpenAI \
  --sku-name Standard --sku-capacity 10
```
