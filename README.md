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

## Prerequisites

Before you begin, you will need the following:
* An **Azure Subscription**. Note: Azure Confidential Computing is not available on free trial accounts.
* **Azure CLI** version 2.46.0 or later.
* **PowerShell** as your command line interface.
* Sufficient **quota** for the VM SKUs used in the tutorials (e.g., DCasv5-series or NCCadsH100_v5-series).


## Tutorials

Get started by choosing one of the following tutorials. Each one is designed to be standalone.

| Tutorial | Description | Key Concepts |
|---|---|---|
| **[Confidential ML Training](tutorials/confidential-ml-training/README.md)** | Learn the fundamentals by deploying a CPU-based Confidential VM. You will train a machine learning model on an encrypted dataset that is only ever decrypted inside the TEE. | ![CVM-Confidential_VM][badge-cvm] ![TEE-Trusted_Execution_Environment][badge-tee] ![Attestation-Guest_Attestation][badge-attest] ![SKR-Secure_Key_Release][badge-skr] ![Policy-Key_Release_Policy][badge-policy] ![Data-Encryption_in_Use][badge-data] ![DES-OS_Disk_Encryption][badge-des] ![XGB-XGBoost][ml-xgb] ![ML-Binary_Classifier][ml-binary] |
| **[Confidential LLM Inferencing](tutorials/confidential-llm-inferencing/README.md)** | Add GPU acceleration to deploy a Large Language Model (LLM) on a Confidential VM with an NVIDIA H100 GPU. This tutorial shows how to protect both the model's weights and user prompts. | ![CGPU-Confidential_GPU_VM][badge-cgpu] ![TEE-Trusted_Execution_Environment][badge-tee] ![Attestation-Guest_Attestation][badge-attest] ![SKR-Secure_Key_Release][badge-skr] ![Attestation-GPU_Attestation][badge-attestation-gpu] ![Model-Model_IP_Protection][badge-modelip] ![TLS-End_to_End_TLS][badge-tls] ![DES-OS_Disk_Encryption][badge-des] ![Client-Streamlit_Client_App][badge-client] ![vLLM-LLM_Inference_Server][ml-vllm] ![Local-LLM][ml-local] ![HF-Hugging_Face][ml-hf] ![AML-AzureML_Registry][ml-aml] |
| **[Confidential Whisper Pipeline](tutorials/confidential-whisper-inferencing/README.md)** | Build a complete, end-to-end secure AI pipeline. This tutorial demonstrates how to securely transcribe sensitive audio using Azure's Confidential Whisper service and analyze the transcript with your confidential LLM. | ![OHTTP-Oblivious_HTTP][badge-ohttp] ![HPKE-Hybrid_Public_Key_Encryption][badge-hpke] ![KMS-Key_Management_Service][badge-kms] ![Whisper-Confidential_Whisper][badge-whisper] ![Pipeline-End_to_End_Pipeline][badge-pipeline] ![Client-Streamlit_Client_App][badge-client] |

<!-- Existing badge refs (flat-square). Adjust colors if you like. -->
[badge-cvm]: https://img.shields.io/badge/CVM-Confidential_VM-6f42c1?style=flat-square
[badge-tee]: https://img.shields.io/badge/TEE-Trusted_Execution_Environment-0b8a9f?style=flat-square
[badge-attest]: https://img.shields.io/badge/Attestation-Guest_Attestation-1f6feb?style=flat-square
[badge-skr]: https://img.shields.io/badge/SKR-Secure_Key_Release-f39c12?style=flat-square
[badge-policy]: https://img.shields.io/badge/Policy-Key_Release_Policy-64748b?style=flat-square
[badge-data]: https://img.shields.io/badge/Data-Encryption_in_Use-2ecc71?style=flat-square
[badge-des]: https://img.shields.io/badge/DES-OS_Disk_Encryption-6366f1?style=flat-square

[badge-cgpu]: https://img.shields.io/badge/CGPU-Confidential_GPU_VM-7c3aed?style=flat-square
[badge-attestation-gpu]: https://img.shields.io/badge/Attestation-GPU_Attestation-475569?style=flat-square
[badge-modelip]: https://img.shields.io/badge/Model-Model_IP_Protection-8e44ad?style=flat-square
[badge-tls]: https://img.shields.io/badge/TLS-End_to_End_TLS-10b981?style=flat-square

[badge-ohttp]: https://img.shields.io/badge/OHTTP-Attested_Oblivious_HTTP-0ea5e9?style=flat-square
[badge-hpke]: https://img.shields.io/badge/HPKE-Hybrid_Public_Key_Encryption-06b6d4?style=flat-square
[badge-kms]: https://img.shields.io/badge/KMS-Key_Management_Service-10b981?style=flat-square
[badge-whisper]: https://img.shields.io/badge/Whisper-Confidential_Whisper-d946ef?style=flat-square
[badge-pipeline]: https://img.shields.io/badge/Pipeline-End_to_End_Pipeline-7c3aed?style=flat-square
[badge-client]: https://img.shields.io/badge/Client-Streamlit_Client_App-94a3b8?style=flat-square

<!-- NEW ML badge refs -->
[ml-xgb]: https://img.shields.io/badge/XGB-XGBoost-22c55e?style=flat-square
[ml-binary]: https://img.shields.io/badge/ML-Binary_Classifier-16a34a?style=flat-square

[ml-vllm]: https://img.shields.io/badge/vLLM-LLM_Inference_Server-0ea5e9?style=flat-square
[ml-local]: https://img.shields.io/badge/Local-LLM-0891b2?style=flat-square
[ml-hf]: https://img.shields.io/badge/HF-Hugging_Face-38bdf8?style=flat-square
[ml-aml]: https://img.shields.io/badge/AML-AzureML_Registry-0284c7?style=flat-square


## Contributing

This project welcomes contributions and suggestions.  

For the contributions, this project endorses the [Microsoft Enterprise AI Services Code of Conduct](https://learn.microsoft.com/en-us/legal/ai-code-of-conduct), which defines the requirements that all customers of Microsoft AI Services (as defined in the [Microsoft Product Terms](https://microsoft.com/licensing/terms/)) must adhere to in good faith, in terms of [responsible AI](https://www.microsoft.com/en-us/ai/responsible-ai) requirements, usage restrictions, content requirements, as well as additional conduct requirements if any for specific Microsoft AI services being leveraged in the tutorials, modules, and other assets of this project.

Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.

## Legal notices

Microsoft and any contributors grant you a license to the Microsoft documentation and other content in this project under the [Creative Commons Attribution 4.0 International Public License](https://creativecommons.org/licenses/by/4.0/legalcode), see the [LICENSE](https://github.com/microsoft/confidential-ai-workshop/blob/main/LICENSE) file, and grant you a license to any code in the repository under the [MIT License](https://opensource.org/licenses/MIT), see the [LICENSE-CODE](https://github.com/microsoft/confidential-ai-workshop/blob/main/LICENSE-CODE) file.

Privacy information can be found at https://privacy.microsoft.com/en-us/.

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents, or trademarks, whether by implication, estoppel or otherwise.
