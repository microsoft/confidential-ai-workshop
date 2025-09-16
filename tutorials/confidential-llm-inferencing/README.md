# Tutorial : Confidential GPU VMs – Secure LLM Inference on NVIDIA H100
> **Focus**: In this tutorial, we demonstrate Azure's new capability: Confidential GPU VMs using NVIDIA's H100 Tensor Core GPU. This part is particularly exciting for AI use-cases because it allows running large ML models (like deep neural networks, large language models) with the same confidentiality guarantees we saw on CPU but now extends to GPU workloads. We will deploy a Confidential VM with an attached H100 GPU ([Azure's NCc series](https://azure.microsoft.com/en-us/blog/how-azure-is-ensuring-the-future-of-gpus-is-confidential/?msockid=2a5e7f6d63ca67d3000a697162ed6667), e.g., [Standard_NCC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nccadsh100v5-series?tabs=sizebasic)) and run an AI inference service on it. We'll show how the model's weights and the user's inputs (prompts) are protected.

## Why Confidential GPUs for AI?
Many AI workloads require GPUs for efficient computation. Until recently, confidential computing was CPU-only, meaning you couldn't process large neural nets without exposing data to the GPU. Now, with [NVIDIA's confidential computing features on H100 GPUs](https://developer.nvidia.com/blog/confidential-computing-on-h100-gpus-for-secure-and-trustworthy-ai/), the [TEE](https://learn.microsoft.com/en-us/azure/confidential-computing/trusted-execution-environment) extends to GPU memory as well. This is critical for AI for several reasons.

### Model Protection
AI models (especially large language models or proprietary models) are valuable IP. When loaded on a GPU normally, their weights sit in GPU memory and could be read by someone with low-level access. Confidential GPUs keep those weights encrypted except within the GPU's secure memory, protecting the model from theft.

### Sensitive Data
The data fed into AI models (prompts, images, patient data for analysis, etc.) might be sensitive. In standard inference servers, you'd have to trust the service operator not to log or misuse this data. With confidential GPU VMs, you don't need to trust – the data is encrypted in transit to the GPU and only processed inside the GPU's TEE. Even the cloud operator can't intercept it in usable form.

### Regulatory and Customer Trust
Organizations can use powerful AI models on confidential data (like analyzing medical images or financial records with an AI) while meeting privacy requirements. End-users (e.g., a hospital sending patient data for AI diagnosis) get cryptographic assurance their data won't leak beyond authorized processing.

In essence, Confidential GPUs enable "Confidential AI" – AI that's privacy-preserving and secure end-to-end. Many of the reasons to use confidential computing in the first place apply strongly here.

## Scenario & Key Concepts
We'll outline a scenario where we deploy a language model inference service on a confidential GPU VM. In this scenario, we will consider a model that has been fully trained and instructed to be used as a chat bot such as [Phi-4-mini-reasoning]([https://github](https://github.com/marketplace/models/azureml/Phi-4-mini-reasoning)) (we suppose that this model is proprietary and the user queries might contain private data). We want to ensure:
1. The model weights are not exposed to Azure or any outside party.
2. The user's prompts and the model's responses are not visible to anyone except the user (and the TEE doing the processing).
3. Only verified code can run on this VM (so that, for instance, an attacker cannot inject their own code to exfiltrate data).

We will achieve this by leveraging the following concepts:
- **Confidential VM with H100 GPU**: This is an Azure virtual machine that runs entirely within a TEE. We will use an instance based on [AMD SEV-SNP](https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/SEV-SNP-strengthening-vm-isolation-with-integrity-protection-and-more.pdf) technology. The unique feature here is the addition of an NVIDIA H100 GPU that extends this TEE. The communication between the CPU and GPU is encrypted over the PCIe bus, and data is only decrypted inside the GPU's secure computing units. This allows us to run demanding AI applications without code modification, while benefiting from comprehensive hardware protection.
- **Guest Attestation & Double Attestation (VM + GPU)**: Attestation is the process by which our VM proves its identity and integrity. It's called "[Guest Attestation](https://learn.microsoft.com/en-us/azure/confidential-computing/guest-attestation-confidential-vms)" because the guest operating system (the "guest") initiates this verification. In our case, it's a double attestation:
    - The VM proves to [Microsoft Azure Attestation (MAA)](https://learn.microsoft.com/en-us/azure/attestation/overview) that it is an authentic CVM, with the correct firmware and secure boot enabled.
    - Inside the VM, a verification process ensures that the GPU is also authentic, that its drivers have not been tampered with, and that it is operating in confidential mode. Our application will combine these two attestations to achieve complete trust in the environment.
- **Secure Key Release (SKR)**: This is the [mechanism](https://learn.microsoft.com/en-us/azure/confidential-computing/concept-skr-attestation) by which [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview) (Premium SKU) releases a [secret](https://learn.microsoft.com/en-us/azure/key-vault/secrets/about-secrets) (our model key decryption key) only to an application running in a [TEE](https://learn.microsoft.com/en-us/azure/confidential-computing/trusted-execution-environment) that has successfully passed its [attestation process](https://learn.microsoft.com/en-us/azure/confidential-computing/guest-attestation-confidential-vms). The key is delivered in an encrypted format and can only be decrypted by the [virtual TPM](https://learn.microsoft.com/en-us/azure/confidential-computing/how-to-leverage-virtual-tpms-in-azure-confidential-vms) (vTPM) of the VM that requested it.
- **Key Release Policy**: This is the security contract we attach to our key in Key Vault. It defines the [precise requirements](https://docs.azure.cn/en-us/key-vault/keys/policy-grammar) that the VM's attestation report must meet. For a GPU, this policy is stricter and must include claims about the state of both the VM and the GPU.

<details>
<summary>Click here to expand if you want to deep dive even more in those concepts</summary>

- DEK, KEK and Master Key Management:
  - [Azure Data Encryption at Rest](https://learn.microsoft.com/en-us/azure/security/fundamentals/encryption-atrest)
  - [Unbderstanding DEK and KEK in Encryption](https://zerotohero.dev/inbox/dek-kek/)

- Confidential VM:
  - [About Azure confidential VMs](https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-vm-overview)
  - [Azure Confidential VM options](https://learn.microsoft.com/en-us/azure/confidential-computing/virtual-machine-options)
  - [Thomas Van Laere | Azure Confidential Computing: IaaS](https://thomasvanlaere.com/posts/2022/04/azure-confidential-computing-iaas/)

- Os disk encryption with Customer Managed Key (CMK)
  - [Azure Confidential computing VM and OS disk encryption through HSM backed key CMK](https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/azure-confidential-computing-vm-and-os-disk-encryption-through-hsm-backed-key-cm/4408926)

- Attestation:
  - [Azure Attestation Overview](https://learn.microsoft.com/en-us/azure/confidential-computing/attestation-overview)
  - [Example of an Azure Attestation token](https://learn.microsoft.com/en-us/azure/attestation/attestation-token-examples#sample-jwt-generated-for-sev-snp-attestation)

- Secure Key Release:
  - [Azure Key Vault Overview](https://learn.microsoft.com/en-us/azure/key-vault/general/overview)
  - [What is Azure Key Vault?](https://learn.microsoft.com/en-us/azure/key-vault/general/basic-concepts)
  - [Secure Key Release with Azure Key Vault and Azure Confidential Computing](https://learn.microsoft.com/en-us/azure/confidential-computing/concept-skr-attestation)
  - [Azure Key Vault secure key release policy grammar](https://learn.microsoft.com/en-us/azure/key-vault/keys/policy-grammar)

- Application/script running within a TEE doing a remote attestation:
  - [Secure Key Release with Azure Key Vault and application on Confidential VMs with AMD SEV-SNP](https://learn.microsoft.com/en-us/azure/confidential-computing/skr-flow-confidential-vm-sev-snp?tabs=windows)
  - [What is guest attestation for confidential VMs?](https://learn.microsoft.com/en-us/azure/confidential-computing/guest-attestation-confidential-vms)
  - [Thomas Van Laere | Azure Confidential Computing: Secure Key Release](https://thomasvanlaere.com/posts/2022/12/azure-confidential-computing-secure-key-release/)
  - [Thomas Van Laere | Azure Confidential Computing: Secure Key Release Part 2](https://thomasvanlaere.com/posts/2023/10/azure-confidential-computing-secure-key-release-part-2/)
- Confidential AI:
  - [Confidential AI Overview](https://learn.microsoft.com/en-us/azure/confidential-computing/confidential-ai)
  - [Azure AI Confidential Inferencing: Technical Deep-Dive](https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/azure-ai-confidential-inferencing-technical-deep-dive/4253150)
- CGPU VM:
  - [Azure Confidential GPU options](https://learn.microsoft.com/en-us/azure/confidential-computing/gpu-options)
  - [Thomas Van Laere | Azure Confidential Computing: Confidential GPUs and AI](https://thomasvanlaere.com/posts/2025/03/azure-confidential-computing-confidential-gpus-and-ai/)

</details>

### 1. Prerequisites and Environment Preparation

First, we need to establish the foundational requirements for confidential GPU computing, which are significantly more complex than standard confidential VMs due to specialized hardware and driver requirements.

Confidential GPU VMs represent the cutting edge of Azure's confidential computing offerings. Unlike CPU-only confidential VMs that can use standard Ubuntu images, GPU confidential computing requires specific VM series, specialized NVIDIA drivers, and careful quota management. The `Standard_NCC40ads_H100_v5` series is currently the primary offering for confidential GPU workloads, featuring AMD SEV-SNP for CPU confidentiality combined with NVIDIA's H100 Confidential Computing mode.

#### 1.1 Azure Subscription and Quota Verification

First, let's define the environment variables and prerequisites for this tutorial.

```powershell
$RESOURCE_GROUP="confidential-ai-gpu-rg"
$LOCATION = "eastus2"
$VM_SKU = "Standard_NCC40ads_H100_v5"
$VNET_NAME="confidential-ai-gpu-vnet"
$VM_NAME="confidential-gpu-vm"
$KV_NAME="cgpukv-$(Get-Random)"
$ADMIN_USERNAME="azureuser"
$SSH_KEY_PATH="$HOME\.ssh\id_rsa.pub"
```

**Key Decision Points**:
- **Region Selection**: We'll use East US 2 (`eastus2`) in this tutorial as our primary region where confidential GPU VMs are available. You can choose another region, but ensure it supports the `Standard_NCC40ads_H100_v5` SKU. To check if your preferred region supports this SKU you can check on [Azure's VM sizes documentation](https://azure.microsoft.com/en-US/explore/global-infrastructure/products-by-region/table) and search for `NCCadsH100_v5-series`.

- **Quota Requirements**: H100 VMs require special quota approval. Standard Azure subscriptions don't have access to these SKUs by default, requiring a quota increase request that can take several business days to process.

First, let's verify your Azure subscription and check current quotas. Open PowerShell as Administrator and run:

```powershell
# Login to Azure (this will open a browser window)
az login

# Verify your subscription details
az account show --output table

# Set your subscription (replace with your subscription ID)
$SUBSCRIPTION_ID = "<your-subscription-id-here>"
az account set --subscription $SUBSCRIPTION_ID
```

Now, let's check the crucial quota requirements for confidential GPU VMs:

```powershell
# Check current quota usage for NCC series (Confidential GPU VMs)
az vm list-usage --location $LOCATION --query "[?contains(name.value, 'NCC')]" --output table

# Check specifically for Standard_NCC40ads_H100_v5 cores
az vm list-usage --location $LOCATION --query "[?name.value=='StandardNCCads2023Family']" --output table
```
You should expect to see this kind of output:
```powershell
CurrentValue    Limit    LocalName
--------------  -------  --------------------------------
0               40       Standard NCCads2023 Family vCPUs
```

If your quota shows 0 (Limit is 0) for `StandardNCCads2023Family` cores, you'll need to request a quota increase.

> [!IMPORTANT]
> If you don't see the `Standard NCCads2023 Family vCPUs` SKU listed, or your quota is 0, you must request a quota increase through the Azure portal. This process can take few business days. Navigate to **Subscriptions → Usage + quotas → Request increase** and request at least **40** cores for the "Standard NCCads H100 Family" in your chosen region.

#### 1.2 Azure CLI Version and Environment Setup

Confidential GPU VMs require Azure CLI version 2.46.0 or later due to new GPU-specific parameters and attestation features:

```powershell
az --version
```
If you need to upgrade you can run this command (recommended to always use latest):
```powershell
az upgrade
```

#### 1.3 Next Steps Preparation

With the prerequisites established, we're ready to move forward. In the next step, we'll configure Azure Key Vault with secure key release policies specifically tailored for GPU attestation. 

The main differences you'll notice compared to Tutorial 1:
- SKR policies must account for both CPU and GPU attestation claims
- VM deployment requires additional GPU-specific parameters
- The onboarding process includes GPU driver installation and configuration
- Attestation verification encompasses both hardware components

**Checkpoint**: Before proceeding to Step 2, ensure you have:
- [x] Azure CLI 2.38.0+ installed and configured
- [x] Quota approved for `Standard_NCC40ads_H100_v5` (40 cores minimum)


### 2. Create a Resource Group

In Azure, all resources must reside in a resource group, which serves as a logical container. Let's create one for this tutorial.
```shell
az group create --name $RESOURCE_GROUP --location $LOCATION
```

**Expected Output:**
The command will return a JSON object confirming that the resource group was created successfully. The `provisioningState` should be `Succeeded`.
```json
{
  "id": "/subscriptions/<your-subscription-id>/resourceGroups/MyConfidentialRG",
  "location": "eastus2",
  "managedBy": null,
  "name": "confidential-ai-gpu-rg",
  "properties": {
    "provisioningState": "Succeeded"
  },
  "tags": null,
  "type": "Microsoft.Resources/resourceGroups"
}
```

### 3 Create a Virtual Network

To deploy a confidential GPU VM, we need a virtual network (VNet) to host the VM. This VNet will allow secure communication between the VM and other Azure resources.

```powershell
az network vnet create `
  --resource-group $RESOURCE_GROUP `
  --name $VNET_NAME `
  --address-prefix "10.2.0.0/16" `
  --subnet-name "default" `
  --subnet-prefix "10.2.0.0/24"
```

### 4. Secure Key Vault and Attestation Policy Configuration

To set up a CPU+GPU **Confidential VM**, we use a **double-attestation** pattern that cleanly separates what **Azure Key Vault Secure Key Release (SKR)** enforces from what we verify **in-guest**. As of now, MAA does not support verifying GPU attestation evidence or including GPU-specific claims in its tokens but it can be performed independently (see [Azure AI Confidential Inferencing: Technical Deep-Dive](https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/azure-ai-confidential-inferencing-technical-deep-dive/4253150#:~:text=Applications%20within%20the%20VM%20can,when%20the%20GPU%20is%20reset)). Hence, SKR evaluates MAA evidence for the SEV-SNP CVM (CPU/vTPM), and we verify the GPU separately. This gives us strong end-to-end guarantees without requiring GPU claims in SKR policies.

Concretely:

* **SKR policy** matches claims from the MAA token for a **SEV-SNP CVM** (e.g., `x-ms-isolation-tee.x-ms-attestation-type`, `x-ms-isolation-tee.x-ms-compliance-status`, and optional vTPM assertions). If these checks pass, Key Vault releases the wrapping key.
* **In-guest GPU attestation** then confirms the **NVIDIA H100** is in the expected confidential mode with approved firmware before the app uses the released key or loads model weights.

> [!NOTE]
> For GPU verification we use the *Local GPU Verifier* from the [Azure/az-cgpu-onboarding](https://github.com/Azure/az-cgpu-onboarding) repo (we will cover that in step [8.4. Verify GPU Attestation](https://github.com/microsoft/confidential-ai-workshop/blob/initial-tutorials/tutorials/confidential-llm-inferencing/README.md#84-verify-gpu-attestation) of this tutorial). You will be able to run it at startup and any time later to (re)check the GPU state.

By combining **SKR (CPU/vTPM)** with **local GPU attestation**, keys are released only to a compliant CVM *and* are usable only when the GPU is also in a verified confidential state—exactly what we need for confidential AI workloads.


#### 4.1 Create the Key Vault

Similar to the [Confidential ML Training](../confidential-ml-training/README.md) tutorial, we'll create a Azure Key Vault Premium setup.

> [!TIP]
> For storing and managing cryptographic keys in production, **Azure Managed HSM** is the recommended best practice. It offers a fully managed, highly available, single-tenant, standards-compliant HSM service. However, compared to Premium SKU of Azure Key Vault, it comes at a higher cost. If you are interested in using Managed HSM, please refer to the module [Secure Key Release set-up with Managed HSM](../../modules/key-management/Managed-HSM.md).

Now create the resource group and Key Vault:
```powershell
az keyvault create `
  --name $KV_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku "Premium" `
  --enable-rbac-authorization true `
  --enable-purge-protection true

# Verify Key Vault creation and note the URI
az keyvault show --name $KV_NAME --query "properties.vaultUri" --output tsv
```

> [!NOTE]
> If you are using a new or clean Azure subscription, you might need to register the `Microsoft.KeyVault` resource provider first. If you receive a `MissingSubscriptionRegistration` error, run the following command and wait for it to complete (this can take a few minutes):
> ```powershell
> az provider register --namespace Microsoft.KeyVault
> ```
> You can check the status with:
> ```powershell
> az provider show --namespace Microsoft.KeyVault --query "registrationState"
> ```
> Once it shows "Registered", you can proceed to create the Key Vault.



#### 4.2. Assign Permissions to Key Vault
Now that we have our Key Vault, we need to assign the necessary permissions to the Key Vault for the current user:

```powershell
# Assign permissions to the Key Vault
$CURRENT_USER_ID = $(az ad signed-in-user show --query "id" -o tsv)
if (-not $CURRENT_USER_ID) {
    throw "Could not retrieve user ID. Make sure you are logged in with 'az login'."
}
$KV_SCOPE = $(az keyvault show --name $KV_NAME --resource-group $RESOURCE_GROUP --query "id" -o tsv)

az role assignment create `
  --role "Key Vault Crypto Officer" `
  --assignee-object-id $CURRENT_USER_ID `
  --assignee-principal-type "User" `
  --scope $KV_SCOPE
```
#### 4.3. Definition of the release Policy
The Secure Key Release (SKR) policy is a JSON document that defines the conditions under which a key can be released from the Key Vault. For GPU confidential VMs, this policy must in clude claims that validate both the CPU and GPU attestation reports. Create a JSON file with the following content in your working environment:

```json
{
  "version": "1.0.0",
  "anyOf": [
    {
      "authority": "sharedeus2.eus2.attest.azure.net",
      "allOf": [
        {
          "claim": "x-ms-isolation-tee.x-ms-attestation-type",
          "equals": "sevsnpvm"
        },
        {
          "claim": "x-ms-isolation-tee.x-ms-compliance-status",
          "equals": "azure-compliant-cvm"
        }
      ]
    }
  ]
}
```

> [!NOTE]
> The above SKR policy is using a shared attestation provider endpoint (e.g. `sharedeus2.eus2.attest.azure.net`). This is a common endpoint provided by Azure for confidential VMs. You can also use a dedicated attestation provider if you have one set up.
> The claims corresponds to the following:
> - `x-ms-isolation-tee.x-ms-attestation-type`: **Is this a real Confidential VM?** The policy first checks if the request is coming from a genuine Azure Confidential VM using AMD's security technology (sevsnpvm). This is like checking the ID card to make sure it's the right type.
> - `x-ms-isolation-tee.x-ms-compliance-status`: **Is it configured securely?** It then verifies that the VM is "Azure compliant," meaning security features like Secure Boot are enabled. This is like making sure the ID card hasn't been tampered with.

Store the authority URL for later use:
```powershell
$ATTEST_URL = "https://sharedeus2.eus2.attest.azure.net"
```

> [!TIP]
> Need a **dedicated attestation provider** instead of the shared endpoint?
> Follow: [Provision a Dedicated Microsoft Azure Attestation Provider](../../modules/attestation/custom-attestation-provider.md),
> then set the `authority` in `release-policy.json` to your attestation URL and store it in `$ATTEST_URL`.

#### 4.4. Create the wrapping key
Now we will create the key that will be used to wrap the model encryption key with the policy that we defined earlier. This key will be used to encrypt the model weights and will be stored in the Key Vault.

Let's define a variable for our key name:
```powershell

$KEK_NAME="KeyEncryptionKey"
```

Now we create the key using our `release-policy`:

```powershell
az keyvault key create `
    --vault-name $KV_NAME `
    --name $KEK_NAME `
    --kty "RSA-HSM" `
    --exportable `
    --policy "@release-policy.json"
```

> [!TIP]
> Bringing your **own key material (BYOK)** instead of creating a new KEK here?
> Use: [Bring Your Own Key (import to AKV/MHSM)](../../modules/key-origin/bringing-your-own-key.md) *(module coming soon)*,
> then skip the key creation below and continue with the verification step using your imported key.


#### 4.5. Verify Key Creation and store its identifiers
Now let's verify that the key was created successfully and that the SKR policy is applied correctly:

```powershell
$keyJson = az keyvault key show --vault-name $KV_NAME --name $KEK_NAME -o json | ConvertFrom-Json
$KEK_KID = $keyJson.key.kid
```
This command should return the Key ID of the wrapping key, confirming it was created successfully.

Store the KEK identifiers for later use:
```powershell
$VAULT_ID = az keyvault show --name $KV_NAME --query id -o tsv
$KEK_RESOURCE = "$VAULT_ID/keys/$KEK_NAME"
```

#### 4.6. (Optional) Configure OS Disk Encryption with Customer‑Managed Keys

> [!TIP]
> Need OS-disk encryption with your own keys (CMK)?
> Use one of the following modules based on your preferred key management solution: 
> | Key Management Service | Module |
> |-----------------------|--------|
>  | Azure Key Vault       | [OS Disk Encryption with Customer-Managed Keys (DES)](../../modules/os-disk-encryption/os-disk-encryption-cmk.md) |
> | Azure Managed HSM     | [OS Disk Encryption with Customer-Managed Keys (DES) using Managed HSM](../../modules/os-disk-encryption/os-disk-encryption-cmk-mhsm.md) |
> 
> Then return here to continue deployment.


### 5. Deploy the Confidential GPU VM
Now that we encrypted our model and wrapped the key, we can deploy the confidential GPU VM. This step involves creating the VM with the necessary configurations to support confidential computing and GPU acceleration.

#### 5.1. Deploy the Confidential GPU VM
We will use the Azure CLI to deploy a Confidential GPU VM with the `Standard_NCC40ads_H100_v5` SKU. This VM will have the necessary configurations for confidential computing, including secure boot, vTPM, and managed identity.
```powershell
az vm create `
  --resource-group $RESOURCE_GROUP `
  --name $VM_NAME `
  --image "Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest" `
  --size $VM_SKU `
  --admin-username $ADMIN_USERNAME `
  --ssh-key-values "$SSH_KEY_PATH" `
  --vnet-name $VNET_NAME `
  --subnet "default" `
  --security-type "ConfidentialVM" `
  --os-disk-size-gb 100 `
  --os-disk-security-encryption-type "DiskWithVMGuestState" `
  --enable-vtpm true `
  --enable-secure-boot true `
  --assign-identity "[system]" `
  --public-ip-sku Standard
```

> [!IMPORTANT]
> Read through this section if you have set your Customer Managed Key for OS disk encryption (DES)
> 
> If you have set your Customer Managed Key (CMK) for OS disk encryption using a Disk Encryption Set (DES), you need to pass another parameter `--os-disk-secure-vm-disk-encryption-set $DES_ID` to the `az vm create` command. This parameter links the VM's OS disk encryption to your specified key in Key Vault:
>
> ```powershell
> az vm create `
>  --resource-group $RESOURCE_GROUP `
>  --name $VM_NAME `
>  --image "Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest" `
>  --size $VM_SKU `
>  --admin-username $ADMIN_USERNAME `
>  --ssh-key-values "$SSH_KEY_PATH" `
>  --vnet-name $VNET_NAME `
>  --subnet "default" `
>  --security-type "ConfidentialVM" `
>  --os-disk-size-gb 100 `
>  --os-disk-security-encryption-type "DiskWithVMGuestState" `
>  --os-disk-secure-vm-disk-encryption-set $DES_ID `
>  --enable-vtpm true `
>  --enable-secure-boot true `
>  --assign-identity "[system]" `
>  --public-ip-sku Standard
> ```
> Make sure to replace `$DES_ID` with the actual resource ID of your Disk Encryption Set

#### 5.2. Assign Key Vault Permissions to the VM's Identity
After the VM is created, we need to assign the Key Vault permissions to the VM's managed identity. This allows the VM to access the Key Vault and retrieve the wrapped model key.

```powershell
$VM_PRINCIPAL_ID = $(az vm identity show --resource-group $RESOURCE_GROUP --name $VM_NAME --query "principalId" -o tsv)
```
Then run the following command to assign the Key Vault permissions:
```powershell
az role assignment create `
  --role "Key Vault Crypto Service Release User" `
  --assignee-object-id $VM_PRINCIPAL_ID `
  --assignee-principal-type "ServicePrincipal" `
  --scope $KEK_RESOURCE
```

> [!NOTE]
> The `Key Vault Crypto Service Release User` role allows the VM to perform key wrapping and unwrapping operations, which is essential for our confidential GPU VM to access the model key securely. In this case, we've granted as the sole permission to the VM to unwrap this specific Key Encryption Key.

Finally, get the Key Vault URI to use later:
```powershell
$VM_PUBLIC_IP = $(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query "publicIps" -o tsv)
```

### 6. Model Preparation
Now that we have our key vault and wrapping key set up, we can prepare our proprietary model for deployment. In this tutorial, we will use the [Phi-4-mini-reasoning](https://huggingface.co/microsoft/Phi-4-mini-reasoning) model as an example. This model is a smaller version of the Phi-4 series and is suitable for demonstration purposes.

To securely store the model, we will first need to have the model files locally, then generate a key to encrypt it and then use our Key Encryption Key (KEK) to "wrap" our local key. This will ensure that the model is securely stored and can only be accessed by our confidential GPU VM.

> [!TIP]
> **Choose your model source** (both paths are supported in this tutorial):
>
> | Source | When to use | Module |
> |---|---|---|
> | **Azure ML Registry** | Models curated in Azure ML Registries | [Download from Azure ML Registry](../../modules/model-sourcing/azure-ml-registry.md) |
> | **Hugging Face Hub** | Public/open models via HF CLI | [Download from Hugging Face Hub](../../modules/model-sourcing/hugging-face-hub.md) |
>
> Each module leaves your local model path in `$MODEL_DIR`. Then continue below to generate a local key, encrypt model files, and **wrap** the key with SKR.

Locate the model files in the `$MODEL_DIR` directory (in our case it is `Phi-4-mini-reasoning`).

```powershell
$MODEL_DIR = "Phi-4-mini-reasoning"
```

To make all of this process, we will create a python script that will handle the model download, key generation, encryption, and wrapping, but feel free to modify it to suit your needs.


#### 6.1. Install Local Python Dependencies
Install the necessary Python packages for encryption and Azure Key Vault interaction:

```powershell
pip install azure-identity==1.23.1 azure-keyvault-keys==4.11.0 pycryptodome==3.23.0
```

#### 6.2. Local Model Preparation Script
Create a Python script named `encrypt_model.py` with the following content:

```python
import os
import sys
import logging
import shutil
import argparse
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Using a larger chunk size can be more efficient for large model files.
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB


def encrypt_file(src_path: Path, dest_path: Path, dek: bytes):
    """
    Encrypts a single file using AES-256-GCM authenticated encryption.

    AES-GCM is chosen because it provides both confidentiality (encryption) and
    integrity/authenticity. The resulting file is structured as:
    [12-byte nonce][encrypted content][16-byte authentication tag]

    Args:
        src_path: Path to the source plaintext file.
        dest_path: Path to write the encrypted output file.
        dek: The 32-byte (256-bit) Data Encryption Key.
    """
    # A 12-byte (96-bit) nonce is recommended for AES-GCM. It must be unique
    # for each encryption operation with the same key.
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()

    with src_path.open("rb") as fin, dest_path.open("wb") as fout:
        # Prepend the nonce to the file, it's needed for decryption.
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            fout.write(encryptor.update(chunk))
        
        # Finalize the encryption and get the authentication tag.
        fout.write(encryptor.finalize())
        # Append the 16-byte tag to the end of the file for integrity checks.
        fout.write(encryptor.tag)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    p = argparse.ArgumentParser(
        description="Archive a model dir, encrypt it locally, then wrap the DEK with a KEK in AKV or Managed HSM."
    )
    p.add_argument(
        "model_directory",
        help="Path to the local model directory to be archived and encrypted."
    )
    p.add_argument(
        "--key-id",
        help=("Full Key ID of the KEK in AKV or MHSM."
              "Ex: https://mymhsm.managedhsm.azure.net/keys/KeyEncryptionKey/<version>"),
    )
    p.add_argument(
        "--output-dir",
        default="encrypted-model-package",
        help="Directory to store the encrypted model package."
    )
    return p.parse_args()


def main():
    # Parse command-line arguments
    args = parse_args()

    # Validate input model directory
    model_dir = Path(args.model_directory)
    if not model_dir.is_dir():
        logging.error(f"Local model directory not found: {model_dir}")
        sys.exit(1)

    # Prepare output directory
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        logging.warning(f"Output directory '{output_dir}' already exists. Deleting it.")
        shutil.rmtree(output_dir)
    output_dir.mkdir()

    # 1) Create a TAR archive of the model directory.
    logging.info(f"Creating TAR archive of '{model_dir}' ...")
    archive_path_str = shutil.make_archive(
        base_name=Path("model_archive"),
        format='tar',
        root_dir=model_dir.parent,
        base_dir=model_dir.name
    )
    archive_path = Path(archive_path_str)
    logging.info(f"Archive created at '{archive_path}'.")

    # 2) Generate a single 256-bit DEK.
    dek = os.urandom(32)
    logging.info("Generated a 256-bit Data Encryption Key (DEK).")

    # 3) Encrypt the TAR with the DEK (AES-256-GCM).
    encrypted_archive_path = output_dir / (archive_path.name + ".enc")
    logging.info(f"Encrypting archive -> '{encrypted_archive_path}' ...")
    encrypt_file(archive_path, encrypted_archive_path, dek)
    logging.info("Encryption complete.")
    archive_path.unlink()  # remove unencrypted TAR

    # 4) Wrap the DEK with the KEK in AKV or MHSM.
    if args.key_id:
        key_id = args.key_id.strip()
        logging.info(f"Using provided Key ID: {key_id}")
    else:
        logging.error("Key ID must be provided via --key-id argument.")
        sys.exit(1)

    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(key_id, credential)

    logging.info(f"Wrapping DEK with RSA_OAEP_256...")
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa_oaep_256, dek)
    wrapped_dek = wrap_result.encrypted_key

    wrapped_key_path = output_dir / "wrapped_model_dek.bin"
    wrapped_key_path.write_bytes(wrapped_dek)
    logging.info(f"Wrapped DEK saved to '{wrapped_key_path}'.")

    # 5) Clear plaintext DEK from memory (best effort).
    del dek

    logging.info(f"\n--- Success ---\nThe directory {output_dir} is ready for secure upload.")


if __name__ == "__main__":
    main()
```

> [!NOTE]
> This script prepares a model for secure deployment using the "envelope encryption" pattern:
>
> 1.  **Archiving**: It first bundles the entire model directory into a single `.tar` file. This simplifies the process to a single data blob.
> 2.  **Data Encryption Key (DEK)**: A strong, symmetric key (AES-256) is generated locally. This key is used to encrypt the `.tar` archive.
> 3.  **Key Encryption Key (KEK)**: A separate, asymmetric key (RSA-HSM) that resides securely within Azure Key Vault and never leaves the hardware security module (HSM).
> 4.  **Wrapping**: The script uses the KEK to encrypt (or "wrap") the DEK. The resulting wrapped DEK is small and safe to store alongside the encrypted model archive.
> 5.  **Unwrapping (on the CVM)**: The confidential VM, after proving its identity via attestation, is the only entity authorized by the KEK's release policy to unwrap the DEK. It can then use the plaintext DEK to decrypt the archive in its protected memory.

#### 6.3. Run the Model Preparation Script
Run the script by passing the model local directory, the Key Vault Name and the Key Encryption Key name as arguments:

```powershell
python encrypt_model.py $MODEL_DIR $KV_NAME $KEK_NAME
```

After the script finishes, you will have a new directory named `encrypted-model-package`. This folder contains the encrypted model archive (`model_archive.tar.enc`) and the wrapped key. It is now safe to transfer this entire folder to your VM.



### 7. Prepare and upload encrypted model and helpers to the VM
Now that we have our confidential GPU VM deployed, we need to upload the encrypted model files and any necessary helper scripts to the VM.

#### 7.1. Prepare a `.env` file
To facilitate the configuration of environment variables inside of the VM, we will create a `.env` file that will contain the necessary variables for our application (e.g., Key Vault URI, model paths, etc.).

First we pass in the name of the model folder inside the model tar that contains the `config.json` file. This will smoothen the usage of vllm inference server that we will use:

```powershell
$MODEL_SUBDIR = "Phi-4-mini-reasoning"
$MODEL_CONFIG_FILE = "config.json"
```

Then we create the `.env` file:
```powershell
@"
# --- SKR / Attestation ---
KEK_KID="$KEK_KID"
ATTEST_URL="$ATTEST_URL"

# --- Encrypted model package ---
ENCRYPTED_PACKAGE_DIR="encrypted-model-package"
ENCRYPTED_ARCHIVE_FILE="model_archive.tar.enc"
WRAPPED_KEY_FILE="wrapped_model_dek.bin"

# --- Model root resolution for vLLM ---
MODEL_SUBDIR="$MODEL_SUBDIR"
MODEL_CONFIG_FILE="$MODEL_CONFIG_FILE"
"@ | Out-File -FilePath .\.env -Encoding ASCII
```

#### 7.2. Upload the Encrypted Model Files
Now we need to upload the entire `encrypted-model-package` directory to the VM. You can use `scp` (Secure Copy Protocol) to transfer the files securely.

```powershell
$VM_PUBLIC_IP = $(az vm show -d --resource-group $RESOURCE_GROUP --name $VM_NAME --query "publicIps" -o tsv)

scp -r ./encrypted-model-package/ .\.env "$($ADMIN_USERNAME)@$($VM_PUBLIC_IP):~"
```

### 8. Prepare the VM Environment
After uploading the model, we need to prepare the VM environment. This includes installing necessary packages, configuring the environment, and ensuring that the VM is ready to run the inference service. 

#### 8.1. Onboarding-Package-Steps

To help us with this, the Azure team has provided a comprehensive onboarding repository named [Azure/az-cgpu-onboarding](https://github.com/Azure/az-cgpu-onboarding) that contains all the necessary scripts and configurations to set up the VM for confidential GPU computing.


First, SSH into the VM:
```powershell
ssh $ADMIN_USERNAME@$VM_PUBLIC_IP
```

Once logged in, we will clone the onboarding repository and run the setup script:

```bash
git clone https://github.com/Azure/az-cgpu-onboarding.git
cd az-cgpu-onboarding/src
```

Now, run the setup scripts to install the necessary packages and configure the environment:

1. Prepare the kernel:
```bash
sudo bash ./step-0-prepare-kernel.sh
```
> [!NOTE]
> Please note that this step will involve a reboot of the VM, so you will need to wait for the VM to come back online before proceeding with the next steps.
> 
2. Install the GPU driver:
```bash
cd ~/az-cgpu-onboarding/src
sudo bash ./step-1-install-gpu-driver.sh
```
3. After the reboot, SSH back into the VM and run the remaining setup scripts. Now we are finally able to run attestation - you will be able to see the attestation message printed at the bottom:
```bash
sudo bash ./step-2-attestation.sh
```
4. Install the GPU tools and libraries. These are tools and packages that will allow you to run various workloads on the GPU.
```bash
cd ~/az-cgpu-onboarding/src
sudo bash ./step-3-install-gpu-tools.sh
```

#### 8.2. Post-Setup Validation Steps
After running the setup scripts, we need to validate that the environment is correctly configured and that the GPU is ready for use.

1. Check whether secureboot is enabled:
```bash
mokutil --sb-state
```
You should obtain:
```
SecureBoot enabled
```

2. Check whether the confidential compute mode (CC Mode) is enabled:
```bash
nvidia-smi conf-compute -f
```
You should obtain:
```
CC status: ON
```
3. Check the confidential compute environment:
```bash
nvidia-smi conf-compute -e
```
You should obtain:
```
CC Environment: PRODUCTION
```

#### 8.3. Install CUDA Toolkit
To run AI workloads on the GPU, we need to install the CUDA toolkit. This toolkit provides the necessary libraries and tools to develop and run GPU-accelerated applications.

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
rm cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12-5
```
Then set the environment variables for CUDA by adding the following lines to your `~/.bashrc` file:

```bash
echo 'export PATH=/usr/local/cuda-12.5/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

#### 8.4. Verify GPU Attestation
To verify that the CGPU is running in the intended state, you can use the tool [local_gpu_verifier](https://github.com/Azure/az-cgpu-onboarding/tree/283feee4d9135767e96e08126c306769d6591334/src/local_gpu_verifier) provided in the onboarding package. This tool checks the GPU's attestation status and ensures that it is operating in a secure and compliant manner.

> [!NOTE]
> If you want the verifier to set the GPU Ready State based on the Attestation results, you will need to elevate the user privileges to root before you execute the rest of the instruction like so:
> ```bash
> sudo -i
> ```
> Otherwise, you can proceed with the next steps without requiring sudo privileges.

Navigate to the `local_gpu_verifier` directory and build the tool:
```bash
cd ~/az-cgpu-onboarding/src/local_gpu_verifier
python3 -m venv ./gpuattestation-env
source ./gpuattestation-env/bin/activate
pip install .
```

Then to run the verifier you can execute the following commands:
```bash
cd ~/az-cgpu-onboarding/src/local_gpu_verifier
source ./gpuattestation-env/bin/activate
python3 -m verifier.cc_admin
```

You should obtain an output similar to this:
```
Generating random nonce in the local GPU Verifier ..
Number of GPUs available : 1
Fetching GPU 0 information from GPU driver.
All GPU Evidences fetched successfully
-----------------------------------
Verifying GPU: GPU-885e135a-0f3f-b153-b66f-93305e9ab546
        Driver version fetched : 570.158.01
        VBIOS version fetched : 96.00.9f.00.04
        Validating GPU certificate chains.
                The firmware ID in the device certificate chain is matching with the one in the attestation report.
                GPU attestation report certificate chain validation successful.
                        The certificate chain revocation status verification successful.
        Authenticating attestation report
                The nonce in the SPDM GET MEASUREMENT request message is matching with the generated nonce.
                Driver version fetched from the attestation report : 570.158.01
                VBIOS version fetched from the attestation report : 96.00.9f.00.04
                Attestation report signature verification successful.
                Attestation report verification successful.
        Authenticating the RIMs.
                Authenticating Driver RIM
                        Fetching the driver RIM from the RIM service.
                        RIM Schema validation passed.
                        driver RIM certificate chain verification successful.
                        The certificate chain revocation status verification successful.
                        driver RIM signature verification successful.
                        Driver RIM verification successful
                Authenticating VBIOS RIM.
                        Fetching the VBIOS RIM from the RIM service.
                        RIM Schema validation passed.
                        vbios RIM certificate chain verification successful.
                        The certificate chain revocation status verification successful.
                        vbios RIM signature verification successful.
                        VBIOS RIM verification successful
        Comparing measurements (runtime vs golden)
                        The runtime measurements are matching with the golden measurements.
                GPU is in expected state.
        GPU 0 with UUID GPU-885e135a-0f3f-b153-b66f-93305e9ab546 verified successfully.
        GPU Ready State is already READY
GPU Attestation is Successful.
```

Here we can see that the GPU attestation is successful and that the GPU is in the expected state.



#### 8.5. Install the Secure Key Release Azure application
To get an asymetric encryption key stored in Azure Keyvault or managed HSM released to our VM, we will use the sample secure key release application from the [confidential-computing-cvm-guest-attestation](https://github.com/Azure/confidential-computing-cvm-guest-attestation) repository.

##### 8.5.1. Update and Install build tools and librairies

```bash
sudo apt-get install -y \
  build-essential cmake git libssl-dev libcurl4-openssl-dev \
  libjsoncpp-dev libboost-all-dev nlohmann-json3-dev
```

##### 8.5.2. Install the Azure Guest Attestation Library
The latest attestation package can be found here [https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/](https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/)
```bash
wget https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/azguestattestation1_1.1.2_amd64.deb
sudo dpkg -i azguestattestation1_1.1.2_amd64.deb
rm azguestattestation1_1.1.2_amd64.deb
```

##### 8.5.3. Build the Secure Key Release Application
Clone the repository:
```bash
git clone https://github.com/Azure/confidential-computing-cvm-guest-attestation.git
cd confidential-computing-cvm-guest-attestation/cvm-securekey-release-app
```
Now we need to build the application:
```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
cp AzureAttestSKR ~/
cd ~
```

You can verify that the application was built successfully and that your environment is ready to perform SKR by running the following:

```bash
cd ~/
source .env
sudo -E ~/AzureAttestSKR -a $ATTEST_URL -k $KEK_KID -c imds -r
```

This command should return:
```output
The released key is of type RSA. It can be used for wrapKey/unwrapKey operations. 
```

> [!TIP]
> If you don't get the expected output, check the logs for more details.
> By default, the `AzureAttestSKR` will not have any `SKR_TRACE_ON` set, so it will not output any debug information. Therefore, you can set the environment variable `SKR_TRACE_ON=1` to either `1` (minimal logs) or `2` (detailed logs) before running the script.
> ```bash
> export SKR_TRACE_ON=1
> sudo -E ~/AzureAttestSKR -a $ATTEST_URL -k $KEK_KID -c imds -r
> ```
> For a working environment you should obtain this kind of output:
> ```
> Tracing is enabled
> Main started
> attestation_url: <ATTEST_URL>
> key_enc_key_url: <KEK_KID>
> akv_credential_source: 0
> op: 3
> Entering Util::ReleaseKey()
> Entering Util::doSKR()
> Entering Util::GetMAAToken()
> Level: Info Tag: AttestatationClientLib ReadAkCertFromTpm:118:Successfully fetched the AK cert from TPM
> Level: Info Tag: AttestatationClientLib IsAkCertRenewalRequired:57:Number of days left in AK cert expiry - -363
> Level: Info Tag: AttestatationClientLib ReadAkCertFromTpm:118:Successfully fetched the AK cert from TPM
> Level: Info Tag: AttestatationClientLib IsAkCertProvisioned:159:Ak Cert issuer name /CN=Global Virtual TPM CA - 03
> Level: Info Tag: AttestatationClientLib ParseURL:608:Attestation URL info - protocol {https}, domain {sharedeus.eus.attest.azure.net}
> Level: Info Tag: AttestatationClientLib Attest:113:Attestation URL - <ATTEST_URL>/attest/AzureGuest?api-version=2020-10-01
> Level: Info Tag: AttestatationClientLib GetOSInfo:622:Retrieving OS Info
> Level: Info Tag: AttestatationClientLib GetIsolationInfo:692:Retrieving Isolation Info
> Level: Debug Tag: AttestatationClientLib GetVCekCert:63:VCek cert received from IMDS successfully
> Level: Info Tag: AttestatationClientLib DecryptMaaToken:391:Successfully Decrypted inner key
> Level: Info Tag: AttestatationClientLib Attest:178:Successfully attested and decrypted response.
> Exiting Util::GetMAAToken()
> MAA Token: eyJ...
> Entering Util::GetIMDSToken()
> AKV resource suffix found in KEKUrl
> IMDS token URL: http://169.254.169.254/metadata/identity/oauth2/token?> api-version=2018-02-01&resource=https://vault.azure.net
> Response: {"access_token":"eyJ...
>
> Access Token: eyJ...
>
> Exiting Util::GetIMDSToken()
> AkvMsiAccessToken: eyJ...
> Entering Util::GetKeyVaultSKRurl()
> Request URI: <KEK_KID>/release?api-version=7.3
>
> Exiting Util::GetKeyVaultSKRurl()
> Entering Util::GetKeyVaultResponse()
> Bearer token: Authorization: Bearer eyJ...
> SKR response: {"value":"eyJ...
> Exiting Util::GetKeyVaultResponse()
> SKR token: eyJ...
> Entering Util::SplitString()
> Exiting Util::SplitString()
> SKR token payload: {"request":{"api-version":"7.3","enc":"CKM_RSA_AES_KEY_WRAP","kid":"<KEK_KID>","nonce":"ADE0101"},"response":{"key":{"key":{"kid":"<KEK_KID>","kty":"RSA","key_ops":["encrypt","decrypt","sign","verify","wrapKey","unwrapKey"],"n":"kqy...
> SKR key_hsm: eyJ...
> Encrypted bytes length: 1480
> Encrypted bytes: fAT...
> Decrypted Transfer key: HH-6Rd...
> 
> Entering decrypt_aes_key_unwrap()
> Exiting decrypt_aes_key_unwrap()
> CMK private key has length=1216
> Decrypted CMK in base64url: MII...
> Decrypted CMK in hex: 308...
> Key release completed successfully.
> The released key is of type RSA. It can be used for wrapKey/unwrapKey operations.
> ```
> After troubleshooting, ensure that you set back `SKR_TRACE_ON=""`.

### 9. The Confidential LLM Inference Application
On the VM, we will now set up the Python environment and the server application. The server's only job is to perform the secure key release, decrypt the model archive on its disk, extract it into protected memory, load the model, and serve inference requests.

#### 9.1. Install Python and Required Packages

First, we need to set up a Python virtual environment:
```bash
cd ~/
sudo apt-get update && sudo apt-get install -y python3-venv
python3 -m venv ccvm-env
source ccvm-env/bin/activate
```

Then, we install Python and the required packages for our FastAPI application and for running our vLLM (in our case `Phi-4-mini-reasoning`). We will use `pip` to install the necessary libraries.

```bash
pip install torch mamba-ssm causal-conv1d transformers accelerate "uvicorn[standard]" fastapi "pydantic" cryptography python-dotenv
pip install flash-attn --no-build-isolation
```

Once we have all of the required packages installed, we can create our FastAPI application. First, we create a small module that handles the secure key release and model decryption based on the `AzureAttestSKR` application (we use `nano` but you can use your favorite text editor):

```bash
nano skr_decrypt.py
```

Then you paste the following python code:

```python
import io
import base64
import tarfile
import subprocess
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

NONCE_LEN = 12 # GCM nonce (96 bits)
TAG_LEN = 16 # GCM tag (128 bits)
DEK_LEN = 32 # AES-256 key, 32 bytes

def unwrap_dek(wrapped_key_path: str, attest_url: str, kek_kid: str) -> bytes:
    """
    Uses AzureAttestSKR to attest, authorize SKR against AKV, and unwrap the model DEK.
    Returns the raw 32-byte DEK.
    """
    p = Path(wrapped_key_path)
    if not p.is_file():
        raise FileNotFoundError(f"Wrapped DEK not found: {p}")

    # The tool expects -s as Base64
    wrapped_b64 = base64.b64encode(p.read_bytes()).decode("ascii")

    cmd = [
        "sudo", "-E", str(Path.home() / "AzureAttestSKR"),
        "-a", attest_url,
        "-k", kek_kid,
        "-c", "imds",
        "-s", wrapped_b64,
        "-u",  # unwrap mode
    ]
    res = subprocess.run(cmd, capture_output=True, check=True)

    out = res.stdout.strip()
    # Either raw 32 bytes or base64 string
    if len(out) == DEK_LEN:
        return bytes(out)

    try:
        decoded = base64.b64decode(out)
        if len(decoded) == DEK_LEN:
            return decoded
    except Exception:
        pass

    raise RuntimeError(
        f"Could not get a {DEK_LEN}-byte DEK from AzureAttestSKR. "
        f"stdout(len={len(out)}): {out[:60]!r}..."
    )

def decrypt_and_extract_archive(encrypted_archive_path: str, dest_dir: str, dek: bytes) -> None:
    """
    Decrypts an AES-GCM file with layout:
        [nonce(12)][ciphertext...][tag(16)]
    and extracts the resulting TAR into dest_dir.
    """
    if len(dek) != DEK_LEN:
        raise ValueError(f"Invalid DEK length: {len(dek)} (expected {DEK_LEN})")

    enc = Path(encrypted_archive_path)
    if not enc.is_file():
        raise FileNotFoundError(f"Encrypted archive not found: {enc}")

    total = enc.stat().st_size
    if total < NONCE_LEN + TAG_LEN + 1:
        raise ValueError("File too small to contain nonce/tag/ciphertext.")

    with enc.open("rb") as f:
        nonce = f.read(NONCE_LEN)
        f.seek(-TAG_LEN, 2)  # from end
        tag = f.read(TAG_LEN)
        f.seek(NONCE_LEN)
        ciphertext = f.read(total - NONCE_LEN - TAG_LEN)

    decryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce, tag)).decryptor()
    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Open the TAR from memory and extract to dest_dir
    bio = io.BytesIO(plaintext)
    with tarfile.open(fileobj=bio, mode="r:*") as tf:
        tf.extractall(path=dest_dir)
```

Now, create a file named `app.py` that will be based on [vLLM](https://github.com/vllm-project/vllm) which is an easy-to-use library for LLM inference and serving:
```bash
nano app.py
```
And paste the following app:

```python
import os
import shutil
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import skr_decrypt

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

ENCRYPTED_PACKAGE_DIR = os.environ.get("ENCRYPTED_PACKAGE_DIR")
ENCRYPTED_ARCHIVE_FILE = os.environ.get("ENCRYPTED_ARCHIVE_FILE")
WRAPPED_KEY_FILE = os.environ.get("WRAPPED_KEY_FILE")
ATTEST_URL = os.environ.get("ATTEST_URL")
KEK_KID = os.environ.get("KEK_KID")

# Subdirectory inside the tar that holds config.json (in the case of the tutorial: "Phi-4-mini-reasoning")
MODEL_SUBDIR = os.environ.get("MODEL_SUBDIR", "Phi-4-mini-reasoning")

DECRYPTED_MODEL_DIR = "/dev/shm/decrypted_model"

def main():
    """
    Main function to orchestrate the secure model loading and serving process.
    1. Unwraps the Data Encryption Key (DEK) using SKR.
    2. Decrypts and extracts the model archive into an in-memory filesystem (/dev/shm).
    3. Starts the vLLM server, binding it to localhost for security.
    4. Ensures cleanup of decrypted files on exit.
    """
    # Basic env sanity
    required = {
        "ENCRYPTED_PACKAGE_DIR": ENCRYPTED_PACKAGE_DIR,
        "ENCRYPTED_ARCHIVE_FILE": ENCRYPTED_ARCHIVE_FILE,
        "WRAPPED_KEY_FILE": WRAPPED_KEY_FILE,
        "ATTEST_URL": ATTEST_URL,
        "KEK_KID": KEK_KID,
        "MODEL_SUBDIR": MODEL_SUBDIR,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")

    dek = None
    try:
        # 1. Unwrap the Data Encryption Key (DEK) using the attestation tool
        logging.info("Unwrapping Data Encryption Key (DEK) via SKR...")
        wrapped_key_path = os.path.join(ENCRYPTED_PACKAGE_DIR, WRAPPED_KEY_FILE)
        dek = skr_decrypt.unwrap_dek(
            wrapped_key_path=wrapped_key_path,
            attest_url=ATTEST_URL,
            kek_kid=KEK_KID,
        )
        logging.info("DEK unwrapped successfully.")

        # 2. Decrypt and extract model archive to /dev/shm (in-memory filesystem)
        if os.path.exists(DECRYPTED_MODEL_DIR):
            shutil.rmtree(DECRYPTED_MODEL_DIR)
        os.makedirs(DECRYPTED_MODEL_DIR)

        logging.info(f"Decrypting and extracting model archive to '{DECRYPTED_MODEL_DIR}'...")
        encrypted_archive_path = os.path.join(ENCRYPTED_PACKAGE_DIR, ENCRYPTED_ARCHIVE_FILE)
        skr_decrypt.decrypt_and_extract_archive(encrypted_archive_path, DECRYPTED_MODEL_DIR, dek)
        logging.info("Model archive has been decrypted and extracted.")

        # Securely delete the plaintext key from memory
        del dek
        logging.info("Plaintext DEK has been cleared from memory.")

        # 3. Build the vLLM model path: /dev/shm/decrypted_model/<MODEL_SUBDIR>
        model_root = os.path.join(DECRYPTED_MODEL_DIR, MODEL_SUBDIR)
        if not os.path.isdir(model_root):
            raise FileNotFoundError(
                f"Model directory not found: {model_root}. "
                f"Check MODEL_SUBDIR and your tar structure."
            )

        # 4. Launch the vLLM server, binding it to localhost
        vllm_cmd = [
            "python3", "-m", "vllm.entrypoints.openai.api_server",
            "--model", model_root,
            "--host", "127.0.0.1",
            "--port", "8000"
        ]

        logging.info(f"Launching vLLM server with model from '{model_root}'...")
        logging.info(f"Command: {' '.join(vllm_cmd)}")

        # This script will wait here until vLLM is terminated
        subprocess.run(vllm_cmd, check=True)

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # 5. Clean up decrypted files
        if os.path.exists(DECRYPTED_MODEL_DIR):
            logging.info(f"Cleaning up decrypted model files from '{DECRYPTED_MODEL_DIR}'...")
            shutil.rmtree(DECRYPTED_MODEL_DIR)
            logging.info("Cleanup complete.")

if __name__ == "__main__":
    main()
```

> [!NOTE]
> This application does the following:
> - On startup, it retrieves the wrapped symmetric key from Azure Key Vault using the VM's managed identity.
> - It unwraps the key, decrypts the model files, and loads the model into memory.
> - It serves a `/v1/chat/completions` endpoint that accepts a prompt and returns generated text using the loaded model.
>

> [!NOTE]
> **A Note on Security: In-Memory Filesystems (`/dev/shm`)**
>
> You'll notice our script decrypts the model to `/dev/shm/decrypted_model`. This is a crucial security choice.
>
> -   **/dev/shm is not a disk**: It is a `tmpfs`, a filesystem that resides entirely in the CVM's RAM. Data written here is never persisted to the OS disk.
> -   **It's inside the TEE**: On an Azure Confidential VM, all RAM is hardware-encrypted and protected. This means the decrypted model files in `/dev/shm` are still within the TEE's confidential boundary, shielded from the host and any external observers.
> -   **Why not stream directly?** The ideal approach would be to stream decrypted bytes directly into the vLLM process. However, vLLM (like many tools) is designed to load models from a filesystem path. Using `/dev/shm` is a secure and pragmatic pattern that provides the filesystem interface tools expect, while keeping the data within protected memory.
> -   **Cleanup is critical**: The `finally` block in our script ensures that the decrypted files are immediately and irrevocably deleted from RAM the moment the server process terminates.


#### 9.3. Run the vLLM server
Now that we have our script for launching the vLLM server ready, let's start it!

```bash
cd ~/
source ccvm-env/bin/activate
python3 app.py
```
This command will start the vLLM server on port 8000, and is accessible from within the VM.

### 10. Testing the Application
At this step our vLLM server is running and we would want to test it by sending a request to the `/v1/chat/completions` endpoint on our local machine. You can use `curl` or any HTTP client to send a POST request to the endpoint from **the inside of the VM** (in another terminal):

```bash
curl http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "/dev/shm/decrypted_model/Phi-4-mini-reasoning",
        "messages": [{"role": "user", "content": "Define Confidential Inferencing"}],
        "max_tokens": 1024,
        "temperature": 0
    }'
```
You should get this output:
```bash
{
  "id": "chatcmpl-c0c6cc8a369f4b119d2d364798a82596",
  "object": "chat.completion",
  "created": 1756129619,
  "model": "/dev/shm/decrypted_model/Phi-4-mini-reasoning",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "<think>\nOkay, so I need to define \"Confidential Inferencing.\" Let me start by breaking down the term. \"Confidential\" relates to privacy or secrecy, so something about keeping information secret. \"Inferencing\" usually refers to the process of reaching conclusions based on reasoning from available information. Maybe it's about making conclusions without having all the data, but in a way that respects confidentiality.\n\nWait, in the context of AI or data handling, inferencing could be the phase where a model makes predictions. So Confidential Inferencing might be about performing these predictions while ensuring that sensitive data isn't exposed. Like, even when the model is running and making predictions, it has to maintain the privacy of the input data. Maybe techniques like differential privacy, encrypted computation, or federated learning are involved here. \n\nBut I should check if there's a standard definition for this. I'm not sure if it's a widely recognized term. Maybe it's used in cybersecurity or data privacy frameworks. Alternatively, it could be related to how inference attacks work, where an attacker tries to deduce information from the model's outputs. So Confidential Inferencing might refer to methods that prevent such attacks, ensuring that even if someone is trying to infer private information through the model's predictions, they can't. \n\nAnother angle: in cloud computing, when you use a remote server for inferencing, the data is sent to the server. Keeping that process confidential would mean that the data isn't leaked during transmission or while processing. So maybe it's about secure inference mechanisms that protect data throughout the inferencing phase. \n\nHmm, perhaps combining elements of secure multi-party computation, where parties can compute a function without revealing their inputs, with model inferencing. That way, the model can make predictions (inferencing) without the raw data ever being exposed. \n\nI should also consider if there's a specific technology or protocol associated with this term. Maybe something like homomorphic encryption, which allows computations on encrypted data. If a model is encrypted and performs inferencing on encrypted data, the results are decrypted without exposing the underlying data. That could be part of Confidential Inferencing. \n\nAlternatively, it might involve anonymization techniques before sending data for inferencing. Removing or obfuscating identifiers to prevent linking back to individuals. \n\nWait, the term might be used in the context of GDPR or other data protection regulations, emphasizing that even during inference (the phase after training where the model is deployed), data privacy must be maintained. So companies need to ensure that their deployed models don't inadvertently leak sensitive information through their outputs or side channels. \n\nSo putting it all together, Confidential Inferencing likely refers to the process of performing machine learning model inferencing in a secure manner that protects confidential information from being exposed, either through the model's predictions, intermediate computations, or any data handling during the inferencing phase. This would involve various cryptographic methods, privacy-preserving algorithms, and secure system designs to ensure that sensitive data remains private throughout the entire inferencing process.\n</think>\n\nConfidential Inferencing is the process of performing machine learning model predictions (inferencing) while ensuring that sensitive or confidential data remains protected throughout. This involves techniques and methodologies that prevent unauthorized disclosure of input data, model internals, or inferred results. Key approaches include:\n\n- **Differential Privacy**: Adding noise to outputs or computations to obscure individual data points.\n- **Homomorphic Encryption**: Enabling computations on encrypted data without decrypting it first.\n- **Federated Learning**: Training models across decentralized devices while keeping raw data local.\n- **Secure Multi-Party Computation**: Allowing collaborative computation without sharing private inputs.\n- **Anonymization/Pseudonymization**: Removing or obfuscating identifiers to protect user identities.\n\nThe goal is to enable actionable insights and predictions without compromising privacy, addressing risks like inference attacks or data leakage in compliance with regulations like GDPR. This ensures that even during deployment and real-world use, confidential information is safeguarded. \n\n\\boxed{Confidential Inferencing \\text{ is the secure process of performing model predictions while protecting sensitive data from exposure through privacy-preserving techniques.}}",
        "refusal": null,
        "annotations": null,
        "audio": null,
        "function_call": null,
        "tool_calls": [],
        "reasoning_content": null
      },
      "logprobs": null,
      "finish_reason": "stop",
      "stop_reason": 200020
    }
  ],
  "service_tier": null,
  "system_fingerprint": null,
  "usage": {
    "prompt_tokens": 22,
    "total_tokens": 852,
    "completion_tokens": 830,
    "prompt_tokens_details": null
  },
  "prompt_logprobs": null,
  "kv_transfer_params": null
}
```

If you managed to get to this step: **Congrats**🥳! 

You have now successfully deployed and tested a confidential AI service using a model that was encrypted locally and only ever decrypted inside a hardware-trusted environment in the cloud.

### 11. Exposing the Confidential LLM Service with TLS

At this point in our journey, we've achieved something remarkable: a fully confidential AI inference service where the model weights are only ever decrypted inside the hardware-protected memory of our Confidential GPU VM. However, our service is currently only accessible from within the VM itself (bound to `127.0.0.1:8000`). 

In this section, we'll learn how to securely expose this service to the internet while maintaining our security guarantees. This involves several critical components that work together to create a production-ready, secure API endpoint.

#### Understanding the Security Architecture

Before diving into implementation, let's understand what we're building and why each component matters:

**The Challenge**: We need to expose our LLM service to external clients while ensuring:
- All communication is encrypted (TLS/HTTPS)
- The inference service remains isolated on the loopback interface
- Only authenticated requests reach our model
- Network attack surface is minimized
- Production-grade reliability and monitoring

**The Solution Stack**:
```
Internet → Azure NSG (80/443 only) → Caddy (TLS termination) → vLLM (127.0.0.1:8000)
```

This architecture ensures that even if an attacker compromises the network layer, they cannot directly access the model service. All external traffic must pass through our security layers.

#### 11.1 Setting Up Public DNS for Your VM

First, we need a stable, memorable address for our service. Azure provides DNS labels that create fully qualified domain names (FQDNs) for public IPs.

**From your local machine:**

```powershell
# Retrieve the public IP resource
$VM_PUBLIC_IP = az vm show -d -g $RESOURCE_GROUP -n $VM_NAME --query "publicIps" -o tsv
$PIP_NAME = az network public-ip list -g $RESOURCE_GROUP --query "[?ipAddress=='$VM_PUBLIC_IP'].name" -o tsv

# Set a DNS label (choose something unique)
$SITE_DNS_LABEL = "my-conf-llm-$(Get-Random -Maximum 9999)"  # Add randomness to ensure uniqueness

# Apply the DNS label
az network public-ip update `
  --resource-group $RESOURCE_GROUP `
  --name $PIP_NAME `
  --dns-name $SITE_DNS_LABEL

# Retrieve the full FQDN
$FQDN = az network public-ip show -g $RESOURCE_GROUP -n $PIP_NAME --query "dnsSettings.fqdn" -o tsv
Write-Host "Your service will be available at: https://$FQDN" -ForegroundColor Green
```

> **What's happening here?** Azure's DNS service automatically creates an A record mapping your chosen subdomain to your VM's public IP. This FQDN remains stable even if you deallocate and reallocate the VM (the IP might change, but the DNS updates automatically).

Expected output:
```
Your service will be available at: https://my-conf-llm-1234.eastus2.cloudapp.azure.com
```

#### 11.2 Hardening Network Security Groups (NSG)

Network Security Groups act as virtual firewalls, controlling traffic at the network layer. We'll configure them to follow the principle of least privilege.

**Understanding NSG Layers**: Azure can apply NSGs at two levels:
1. **NIC-level NSG**: Rules attached directly to the VM's network interface
2. **Subnet-level NSG**: Rules applied to all resources in a subnet

We'll configure both for defense in depth.

**Again from your local machine:**

```powershell
# Get the NIC and its associated NSG
$nicId = az vm show -d -g $RESOURCE_GROUP -n $VM_NAME --query "networkProfile.networkInterfaces[0].id" -o tsv
$nicName = ($nicId -split "/")[-1]
$nicNsgId = az network nic show -g $RESOURCE_GROUP -n $nicName --query "networkSecurityGroup.id" -o tsv

# Create NSG if it doesn't exist
if (-not $nicNsgId) {
    Write-Host "Creating Network Security Group..." -ForegroundColor Yellow
    $nsgName = "${VM_NAME}-nsg"
    az network nsg create --resource-group $RESOURCE_GROUP --name $nsgName
    az network nic update --resource-group $RESOURCE_GROUP --name $nicName --network-security-group $nsgName
} else {
    $nsgName = ($nicNsgId -split "/")[-1]
    Write-Host "Using existing NSG: $nsgName" -ForegroundColor Green
}

# Configure security rules with explicit priorities to avoid conflicts
Write-Host "Configuring NSG rules..." -ForegroundColor Yellow

# Rule 1: Allow HTTPS (port 443) - This is where our API will be served
az network nsg rule create `
  --resource-group $RESOURCE_GROUP `
  --nsg-name $nsgName `
  --name "AllowHTTPS" `
  --priority 100 `
  --access Allow `
  --direction Inbound `
  --protocol Tcp `
  --destination-port-ranges 443 `
  --source-address-prefixes Internet `
  --description "Allow HTTPS for secure API access"

# Rule 2: Allow HTTP (port 80) - Only for Let's Encrypt certificate validation
az network nsg rule create `
  --resource-group $RESOURCE_GROUP `
  --nsg-name $nsgName `
  --name "AllowHTTP-ACME" `
  --priority 110 `
  --access Allow `
  --direction Inbound `
  --protocol Tcp `
  --destination-port-ranges 80 `
  --source-address-prefixes Internet `
  --description "Allow HTTP for ACME certificate validation only"

# Rule 3: Explicitly deny direct access to vLLM port (defense in depth)
az network nsg rule create `
  --resource-group $RESOURCE_GROUP `
  --nsg-name $nsgName `
  --name "DenyDirectModelAccess" `
  --priority 200 `
  --access Deny `
  --direction Inbound `
  --protocol Tcp `
  --destination-port-ranges 8000 `
  --source-address-prefixes Internet `
  --description "Explicitly block direct access to model service"

# Clean up any test rules that might expose internal services
$testRules = @("open-port-8000", "AllowAnyHTTPInbound", "test-rule")
foreach ($rule in $testRules) {
    az network nsg rule delete `
      --resource-group $RESOURCE_GROUP `
      --nsg-name $nsgName `
      --name $rule `
      2>$null  # Suppress errors if rule doesn't exist
}
```

> [!NOTE]
>  We're explicitly allowing only HTTP/HTTPS from the internet. The vLLM service on port 8000 remains bound to localhost and is additionally protected by an explicit deny rule. This defense-in-depth approach ensures multiple security failures would be needed for unauthorized access.

#### 11.3 Implementing TLS with Caddy Reverse Proxy

Now comes the crucial part: setting up a reverse proxy that handles TLS termination and request routing. We'll use Caddy for several reasons:

1. **Automatic HTTPS**: Caddy automatically obtains and renews Let's Encrypt certificates
2. **Security by default**: Modern TLS configurations and security headers out of the box
3. **Simple configuration**: Much simpler than nginx or Apache for our use case
4. **Zero-downtime reloads**: Can update configuration without dropping connections

**SSH into your VM:**
```powershell
ssh $ADMIN_USERNAME@$FQDN
```

**On the VM this time:**

First, let's install Caddy from the official repository:

```bash
# Add Caddy's official repository
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list

chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
chmod o+r /etc/apt/sources.list.d/caddy-stable.list

sudo apt update
sudo apt install caddy
```

Now, let's create a production-grade Caddyfile configuration:

```bash
# Create the Caddyfile with comprehensive security settings
sudo bash -c 'cat > /etc/caddy/Caddyfile << EOF
{
    email admin@example.com
    # debug                 # uncomment if you need verbose ACME/TLS logs
}

<Your Fully qualified domain name for the server> {
    encode gzip

    @root path /
    respond @root 204

    # Simple public healthz (no secret)
    @health path /healthz
    respond @health 200

    # Security headers (browser hardening)
    header {
        # HSTS (adjust max-age when confident)
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
        # You can add CSP if you later serve HTML
    }

    # API key (simple option); see Step 18 for mTLS alternative
    @with_key header X-API-Key {env.API_KEY}
    handle @with_key {
        reverse_proxy 127.0.0.1:8000 {
            header_up Host {host}
            header_up X-Forwarded-Proto {scheme}
        }
    }

    handle {
        respond "Unauthorized" 401
    }
}
EOF'

# Create log directory
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy
```

Now let's set up the API key securely using systemd environment:

```bash
# Generate a strong API key
API_KEY=$(openssl rand -hex 32)
echo "Generated API Key: $API_KEY"
echo "SAVE THIS KEY SECURELY - YOU'LL NEED IT FOR CLIENT ACCESS"

# Configure Caddy service with the API key
sudo mkdir -p /etc/systemd/system/caddy.service.d/
sudo tee /etc/systemd/system/caddy.service.d/override.conf > /dev/null << EOF
[Service]
Environment="API_KEY=$API_KEY"

# Security hardening
PrivateTmp=true
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/caddy /var/log/caddy

# Resource limits
LimitNOFILE=65536
EOF

# Reload systemd and restart Caddy
sudo systemctl daemon-reload
sudo systemctl restart caddy
sudo journalctl -fu caddy
```

Caddy will obtain a **Let’s Encrypt production** certificate (may try `http-01` on 80 or `tls-alpn-01` on 443) and will start serving HTTP→HTTPS redirect and HTTPS on your `$FQDN`.

#### 11.4. Sanity check
Just to check that everything is correctly setted-up, you can use the following command to test the API endpoint:

```bash
Test-NetConnection $FQDN -Port 80
Test-NetConnection $FQDN -Port 443
```

You should expect the 2 endpoints to respond successfully.
```output
ComputerName     : <your-FQDN>
RemoteAddress    : <RemoteAddress>
RemotePort       : 80
InterfaceAlias   : <InterfaceAlias>
SourceAddress    : <SourceAddress>
TcpTestSucceeded : True

ComputerName     : <your-FQDN>
RemoteAddress    : <RemoteAddress>
RemotePort       : 443
InterfaceAlias   : <InterfaceAlias>
SourceAddress    : <SourceAddress>
TcpTestSucceeded : True
```

And you can check that the vLLM server is running and accessible by sending a request to the API endpoint.

```powershell
$headers = @{ "X-API-Key" = "<your-generated-api-key>" }
iwr -Uri "https://$FQDN/v1/models" -Method Get -Headers $headers
```

This request should return a list of available models (in our case only the decrypted model).

```output
StatusCode        : 200
StatusDescription : OK
Content           : {"object":"list","data":[{"id":"/dev/shm/decrypted_model","object":"model","created":1756198923,"owned_by":"vllm","root":"/dev/shm/decrypted_model","pare
                    nt":null,"max_model_len":131072,"permission":[{...
RawContent        : HTTP/1.1 200 OK
                    Alt-Svc: h3=":443"; ma=2592000
                    Referrer-Policy: no-referrer
                    Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
                    X-Content-Type-Options: nosniff
                    X-Frame-Options...
Forms             : {}
Headers           : {[Alt-Svc, h3=":443"; ma=2592000], [Referrer-Policy, no-referrer], [Strict-Transport-Security, max-age=31536000; includeSubDomains; preload],
                    [X-Content-Type-Options, nosniff]...}
Images            : {}
InputFields       : {}
Links             : {}
ParsedHtml        : mshtml.HTMLDocumentClass
RawContentLength  : 500
```

### 12. Client Application for Confidential Inference

Now that our service is exposed via HTTPS, we need a client application that can interact with it properly. We'll build a Streamlit-based web interface that demonstrates best practices for consuming confidential AI services.

#### 12.1 Understanding Client Security Requirements

When building a client for a confidential AI service, we must consider:

1. **End-to-end encryption**: All communication must use TLS
2. **Credential management**: API keys must be handled securely
3. **Response streaming**: Support for real-time token streaming
4. **Error handling**: Graceful handling of network and service errors
5. **User privacy**: No client-side logging of sensitive data

#### 12.2 Building the Streamlit Client

**On your local machine**, create a streamlit client for calling the API endpoint. We have created for you a sample app that you can use as a starting point. You can find it in the [streamlit_client.py](src/streamlit_client.py) file.

#### 12.3 Running and Testing the Client

Once the streamlit client is created, you can run it using the following command:
```powershell
streamlit run streamlit_client.py
```

The client will open in your browser at `http://localhost:8501`. Enter:
- **Server URL**: `https://<your-fqdn>/v1/chat/completions`
- **API Key**: The key generated in [Step 11](#11-exposing-the-confidential-llm-service-with-tls)
- **Model**: `/dev/shm/decrypted_model/Phi-4-mini-reasoning`


### 13. Cleanup
To avoid incurring further costs for these powerful resources, you should delete the entire resource group when you are finished. This will permanently delete the VM, Key Vault, and all other associated resources.

```powershell
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

> [!WARNING]
> This command is irreversible and will delete all resources created in this tutorial.

> [!IMPORTANT]
> If you have set up a managed HSM as your Key Management Solution as described in the module [Provision a Managed HSM for Secure Key Release](../../modules/key-management/Managed-HSM.md), please note that deleting a managed HSM is a two-step process.
> 
> 1. First, you need to delete the managed HSM instance or resource. They then enter a "soft-delete" state for a retention period (the default retention period is 90 days) before they are permanently deleted. During this retention period, you can recover the managed HSM if needed but consider that you will still incur costs for the soft-deleted resources.
>
> 2. Then, to permanently delete the managed HSM or their keys before the retention period ends, you can purge the soft-deleted resources (only if you have not enabled the purge protection feature).
>
> #### Deleting and Purging a Managed HSM
> Here are the commands to delete and purge a managed HSM:
> ```powershell
> az keyvault delete -g $RESOURCE_GROUP --hsm-name $HSM_NAME
> ```
> The managed HSM will be in a soft-deleted state after this command.
> Now to permanently delete it, use:
> ```powershell
> az keyvault purge -g $RESOURCE_GROUP --hsm-name $HSM_NAME
> ```
> #### Deleting and Purging a Managed HSM Key
> If you want to delete and purge a specific key within the managed HSM, you can do so with the following commands:
> ```powershell
> az keyvault key delete --hsm-name $HSM_NAME --name $KEY_NAME
> ```
> This command deletes the key and puts it in a soft-deleted state.
> To permanently delete the key, use:
> ```powershell
> az keyvault key purge --hsm-name $HSM_NAME --name $KEY_NAME
> ```
> Again, this will permanently remove the key from the managed HSM.
> Make sure to replace `$HSM_NAME` and `$KEY_NAME` with the actual names of your managed HSM and key.
> For a more detailed explanation, please refer to the official documentation on [Managed HSM soft-delete and purge protection](https://learn.microsoft.com/en-us/azure/key-vault/managed-hsm/recovery?tabs=azure-cli).
