# OS Disk Encryption for Confidential VMs

## Overview

Confidential VMs support OS‑disk encryption using either **platform‑managed keys (PMK)** or **customer‑managed keys (CMK)**. With CMK, you control the encryption key in Azure Key Vault or Managed HSM and reference it through a **Disk Encryption Set (DES)**.

## Choose your path

| Option                          | When to choose                                                        | Module                                                                                                                                             |
| ------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Platform‑Managed Keys (PMK)** | Simpler setup; you don’t need control over the key lifecycle.         | Use Azure’s default encryption (no extra steps in this repo).                                                                                             |
| **Customer‑Managed Keys (CMK)** | You need key ownership, rotation, revocation, or compliance controls. | Provision a **Disk Encryption Set** that points to your Key Vault key and grant the required RBAC roles. See [Customer‑Managed Key (CMK)](./os-disk-encryption-cmk.md) module. |

> DES can be used across both CPU and GPU Confidential VM tutorials in this repository.

## Prerequisites

* Azure subscription and permissions to create Key Vault, role assignments, and Disk Encryption Sets.
* Azure CLI installed and logged in (`az login`).
* Resource group and region variables set in your shell, e.g.:

  ```powershell
  $RESOURCE_GROUP = "MyConfidentialRG"
  $LOCATION = "westeurope"
  ```

## Continue your tutorial

After finishing your chosen module, return to your tutorial flow:

| Tutorial                               | Continue at                                                                                                                            |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Confidential ML Training (CPU)**     | [4. Deploy the Confidential VM](../../tutorials/confidential-ml-training/README.md#4-deploy-the-confidential-vm)                       |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [5. Deploy the Confidential GPU VM](../../tutorials/confidential-llm-inferencing/README.md#5-deploy-the-confidential-gpu-vm) |
