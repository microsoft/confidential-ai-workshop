# Key Management for Confidential Workloads

## Overview

This folder contains plug‑in modules for key management choices used across the tutorials. Start here to pick your path.

## Choose your path

| Option                        | When to choose                                                                               | Module                                                              |
| ----------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Azure Key Vault (Premium)** | Standard choice for most scenarios; integrates with RBAC and DES; supports release policies. | [Provision Azure Key Vault (Premium)](./Azure-Key-Vault-Premium.md) |
| **Managed HSM**               | (Coming soon) For dedicated, FIPS 140‑2 Level 3 validated HSM requirements.                  | *Not covered in this repo yet.*                                     |

## Reuse across tutorials

The same Key Vault instance can be reused for: OS‑disk encryption (DES/CMK), data key management for training, and model key management for inferencing. Each tutorial will reference this module with a callout and then continue its flow.

## Prerequisites

* Azure CLI installed and logged in (`az login`).
* Permissions to create Key Vaults and assign RBAC roles.
* A resource group and region prepared (see the module for exact variables).

## Continue your tutorial

After completing a key management module, return to the step in your tutorial that first uses the vault (for example, creating a DES for OS‑disk CMK).

| Tutorial                                                 | Continue at                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------- |
| **Confidential ML Training (CPU)**                       | [3.4. Create the release policy file](../../tutorials/confidential-ml-training/README.md#34-create-the-release-policy-file) |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [4.3. Definition of the release policy](../../tutorials/confidential-llm-inferencing/README.md#43-definition-of-the-release-policy) |
