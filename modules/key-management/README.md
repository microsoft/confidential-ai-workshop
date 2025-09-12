# Key Management for Confidential Workloads

## Overview

This folder contains plug‑in modules for key management choices used across the tutorials.

## Microsoft’s commitment​

Azure Key Vault and Azure Key Vault Managed Hardware Security Module (HSM) are designed, deployed and operated such that Microsoft and its agents are precluded from accessing, using or extracting any data stored in the service, including cryptographic keys.​

​
Customer keys that are securely created and/or securely imported into the HSM devices, unless set otherwise by the customer, are not marked extractable and are never visible in plaintext to Microsoft systems, employees, or our agents.​

​
The Key Vault team explicitly does not have operating procedures for granting such access to Microsoft and its agents, even if authorized by a customer.​

​
We will not attempt to defeat customer-controlled encryption features like Azure Key Vault or Azure Key Vault Managed HSM. If faced with a legal demand to do so, we would challenge such a demand on any lawful basis, consistent with our customer commitments as outlined in this [blog](https://blogs.microsoft.com/on-the-issues/2020/11/19/defending-your-data-edpb-gdpr/).​

## Choose your path

| Option                        | When to choose                                                                               | Module                                                              |
| ----------------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Azure Key Vault (Premium)** | Standard choice for most scenarios; integrates with RBAC and DES; supports release policies. | [Provision Azure Key Vault (Premium)](./Azure-Key-Vault-Premium.md) |
| **Managed HSM**               | For dedicated, FIPS 140‑2 Level 3 validated HSM requirements.                  | [Provision Managed HSM](./Managed-HSM.md)                           |

## Reuse across tutorials

The same Key Vault instance can be reused for: OS‑disk encryption (DES/CMK), data key management for training, and model key management for inferencing. Each tutorial will reference this module with a callout and then continue its flow.

## Prerequisites

* Azure CLI installed and logged in (`az login`).
* Permissions to create Key Vaults and assign RBAC roles.
* A resource group and region prepared (see the module for exact variables).

## Continue your tutorial

After completing a key management module, return to the step in your tutorial that first uses the vault (for example, creating a DES for OS‑disk CMK).

| Tutorial                                                 | Continue at                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------ |
| **Confidential ML Training (CPU)**                       | [4. Deploy the Confidential VM](../../tutorials/confidential-ml-training/README.md#4-deploy-the-confidential-vm)                         |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [5. Deploy the Confidential GPU VM](../../tutorials/confidential-llm-inferencing/README.md#5-deploy-the-confidential-gpu-vm)     
