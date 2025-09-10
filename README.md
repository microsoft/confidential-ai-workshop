![Workshop logo](./assets/banner.png)


Welcome to the Confidential AI Workshop! This repository provides a series of hands-on tutorials to help you build and deploy secure and private AI solutions using **[Azure Confidential Computing](https://learn.microsoft.com/en-us/azure/confidential-computing/)**.

> [!CAUTION]
> This repository is intended for educational purposes only. It is not recommended for production use without further security review and customization to meet your specific requirements.

## What is Confidential AI?

Confidential AI is an approach to building AI systems that protects data and models not just at rest and in transit, but also **while in use**. This is achieved by processing data within a hardware-based **Trusted Execution Environment (TEE)**, an encrypted and isolated portion of the CPU or GPU memory.

Inside a TEE, code and data are shielded from the host operating system, the cloud provider, and even system administrators. This enables new possibilities for handling sensitive data, such as:
* Protecting valuable AI model intellectual property (IP) from theft.
* Processing sensitive user data (like medical records or financial information) without exposing it in plaintext.
* Meeting strict regulatory and privacy requirements by providing cryptographic proof of data protection.

## About this Repository

This repository is designed as a hands-on workshop with standalone tutorials and reusable configuration modules. The structure is as follows:

```.
├───assets
├───modules
│   ├───attestation
│   ├───key-management
│   ├───key-origin
│   ├───model-sourcing
│   └───os-disk-encryption
└───tutorials
    ├───confidential-llm-inferencing
    ├───confidential-ml-training
    └───confidential-whisper-inferencing
```

* **[Tutorials](./tutorials)**: Contains the main end-to-end walkthroughs. Each tutorial is self-contained and guides you through building a complete Confidential AI solution.
* **[Modules](./modules)**: Contains focused, reusable guides for specific architectural choices you'll encounter in the tutorials, such as selecting a key management service or configuring OS disk encryption. This modular approach allows you to customize the tutorials to fit your specific security and architecture needs.

## Tutorials

Get started by choosing one of the following tutorials. Each one is designed to be standalone.

| Tutorial | Description | Key Concepts |
|---|---|---|
| ➡️ **[Confidential ML Training](tutorials/confidential-ml-training/README.md)** | Learn the fundamentals by deploying a CPU-based Confidential VM. You will train a machine learning model on an encrypted dataset that is only ever decrypted inside the TEE. | • Confidential VMs (CVM)<br>• Trusted Execution Environment (TEE)<br>• Guest Attestation<br>• Secure Key Release (SKR)<br>• Data Encryption in Use |
| ➡️ **[Confidential LLM Inferencing](tutorials/confidential-llm-inferencing/README.md)** | Add GPU acceleration to deploy a Large Language Model (LLM) on a Confidential VM with an NVIDIA H100 GPU. This tutorial shows how to protect both the model's weights and user prompts. | • Confidential GPU VMs<br>• Trusted Execution Environment (TEE)<br>• Guest Attestation<br>• Secure Key Release<br>• Model IP Protection<br>• End-to-End TLS Encryption |
| ➡️ **[Confidential Whisper Pipeline](tutorials/confidential-whisper-inferencing/README.md)** | Build a complete, end-to-end secure AI pipeline. This tutorial demonstrates how to securely transcribe sensitive audio using Azure's Confidential Whisper service and analyze the transcript with your confidential LLM. | • Oblivious HTTP (OHTTP)<br>• Hybrid Public Key Encryption (HPKE)<br>• Key Management Service (KMS)<br>• Confidential AI Pipelines |

## Prerequisites

Before you begin, you will need the following:
* An **Azure Subscription**. Note: Azure Confidential Computing is not available on free trial accounts.
* **Azure CLI** version 2.46.0 or later.
* **PowerShell** (for local scripts) or a **Bash** terminal.
* Sufficient **quota** for the VM SKUs used in the tutorials (e.g., DCasv5-series or NCCadsH100_v5-series).

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
