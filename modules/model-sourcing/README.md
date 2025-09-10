# Model Sourcing for LLMs

## Overview

Choose how you obtain your base model artifacts before encryption and packaging. These modules plug into Step 6 of the GPU tutorial and can be reused elsewhere.

## Choose your source

| Option                | When to choose                                                                  | Module                                                    |
| --------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **Azure ML Registry** | Models curated in Azure ML Registries. Enterprise controls, private networking. | [Download from Azure ML Registry](./azure-ml-registry.md) |
| **Hugging Face Hub**  | Public/open models from Hugging Face. Simple local download with CLI.           | [Download from Hugging Face Hub](./hugging-face-hub.md)   |

## After completing a module

You will have a **local model directory** ready for encryption and wrapping in the next steps of the tutorial. Each module indicates the exported variables/paths you can use directly.

## Continue your tutorial

| Tutorial                                                 | Continue at                                                                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [6. Model Preparation](../../tutorials/confidential-llm-inferencing/README.md#6-model-preparation) |
