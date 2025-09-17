# Download Model from Azure ML Registry

## Overview

This module downloads a model from an **Azure ML Registry** and reshapes the directory layout for use with **vLLM**.

## Prerequisites

* Azure CLI with the ML extension (`az extension add -n ml`)
* Logged in (`az login`) with access to the registry
* Configuration variables:

```powershell
$MODEL_NAME = "Phi-4-mini-reasoning"
$MODEL_VERSION = 1
$REGISTRY_NAME = "azureml" # Public registry but you can put your own here
$DOWNLOAD_PATH = "./Phi-4-mini-reasoning-azure"
$OUTPUT_DIR = "./Phi-4-mini-reasoning"
```

---

## Procedure

### 1) Download the model from the registry

```powershell
az ml model download `
  --name $MODEL_NAME `
  --version $MODEL_VERSION `
  --registry-name $REGISTRY_NAME `
  --download-path $DOWNLOAD_PATH
```

### 2) Flatten layout for vLLM

What expects a [vllm server](https://docs.vllm.ai/en/v0.8.5.post1/index.html) is to have in the same directory both the tokenizer and the model tensors (along with their respective configuration files). Therefore, to simplify the directory structure, create a new version of the model folder that contains only the content of both the tokenizer and model folders as a single folder.

```powershell
# Create a new directory for the simplified model
mkdir $OUTPUT_DIR

# Move the tokenizer and model folders to the new directory
Get-ChildItem -Path "$DOWNLOAD_PATH/$MODEL_NAME/mlflow_model_folder/components/tokenizer" -Recurse -File | Move-Item -Destination $OUTPUT_DIR
Get-ChildItem -Path "$DOWNLOAD_PATH/$MODEL_NAME/mlflow_model_folder/model" -Recurse -File | Move-Item -Destination $OUTPUT_DIR
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
