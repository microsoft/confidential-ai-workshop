# Download Model from Hugging Face Hub

## Overview

This module downloads a model from **Hugging Face Hub** for local preparation prior to encryption and wrapping.

## Prerequisites

* Python and `pip` available
* Configuration variables:

  ```powershell
  $HF_MODEL     = "microsoft/Phi-4-mini-reasoning"
  $OUTPUT_DIR   = "./Phi-4-mini-reasoning"
  ```

  If the model requires authentication, ensure you have a Hugging Face token set (e.g., `huggingface-cli login`).

---

## Procedure

### 1) Install the Hugging Face CLI

```powershell
pip install -U "huggingface_hub[cli]"
```

### 2) Download the model

```powershell
hf download $HF_MODEL --local-dir $OUTPUT_DIR
```

---

## Exports

After this module, the following is ready for encryption and wrapping in the tutorial:

```powershell
$MODEL_DIR = $OUTPUT_DIR  # e.g., ./Phi-4-mini-reasoning
```

## Continue your tutorial

| Tutorial                                                 | Continue at                                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [6. Model Preparation](../../tutorials/confidential-llm-inferencing/README.md#6-model-preparation) |
