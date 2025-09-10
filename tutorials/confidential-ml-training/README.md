# Confidential VM (CPU) – Foundations and Secure ML Demo

> **Focus**
> This tutorial establishes the foundation. We will create a Confidential VM (CVM) using only CPU (no GPU), and demonstrate a simple machine learning workload using sensitive data. This part introduces core concepts: what Confidential VMs are, how data and code are protected in a TEE, and why attestation and secure key release matter. We'll go step-by-step through deploying a confidential VM with Azure CLI and then run an ML task that operates on encrypted data inside the TEE. The scenario emphasizes why this technology is used over standard VMs.

## Key Features and Concepts

- **Trusted Execution Environment (TEE)**: A hardware-based, attested Trusted Execution Environment (TEE) where the CPU's memory is encrypted and inaccessible to anything outside the enclave/VM. In our case, the entire VM will be a TEE (using AMD SEV-SNP or Intel TDX technology under the hood). Data confidentiality, integrity, and code integrity are assured within this enclave. In practice, this means even Azure's hypervisor or admin accounts cannot snoop on or tamper with what's happening inside your VM's memory.

- **Confidential VM (CVM)**: An Azure Virtual Machine that runs inside a TEE provided by the underlying CPU. Azure offers CVM instances based on AMD Secure Encrypted Virtualization with Secure Nested Paging (SEV-SNP) and on Intel Trust Domain Extensions (TDX). In contrast to process-level enclaves (like Intel SGX, which require code changes), CVMs encapsulate whole VMs – allowing you to run unmodified applications in a confidential manner. This trade-off is a slightly larger trusted computing base (you trust the guest OS and VM stack) for much easier adoption. We will use a CVM so that our regular code (an ML training script) can run without modification, yet still benefit from memory encryption.

- **Attestation**: A critical mechanism that lets us verify the TEE's integrity. Before releasing any confidential data or keys to the VM, we want proof that the VM is indeed running in confidential mode on genuine hardware and that its software stack matches expected known-good measurements. Azure's attestation service (Microsoft Azure Attestation, MAA) provides this proof in the form of cryptographic attestation reports (typically JWTs). In simple terms, attestation answers: "Is this VM truly a Confidential VM running the approved base image and not tampered with?". In our tutorial, we won't dive deeply into manual attestation verification, but it's happening behind the scenes.

- **Data Encryption in Use**: The hallmark of confidential computing. All data processed inside the VM is encrypted in memory and only decrypted within the CPU itself. For example, if our ML model reads sensitive data from disk, that data might be stored encrypted on disk (encryption at rest) and travel over TLS (encryption in transit) to the VM. Once in the VM's memory, it remains encrypted to the outside world – the CPU automatically decrypts it in hardware as the program needs it, and re-encrypts when writing back to RAM. If someone were to inspect the RAM directly (say, a rogue hypervisor or by dumping memory), they'd only see ciphertext. This protection is why we use Confidential VMs: it extends zero-trust to the level of data in use.

- **Secure Key Release (SKR)**: A feature of Azure Key Vault (in its Premium tier or Managed HSM) that works hand-in-hand with confidential VMs. In a confidential scenario, you should keep encryption keys outside of the VM until you're sure the VM is secure. SKR allows Key Vault to release a secret key directly to a trusted enclave/VM after verifying an attestation. The key itself is never exposed to any outside entity; it's delivered only into the TEE. In our tutorial, we'll use SKR to provide a decryption key to our application inside the CVM. This way, we can encrypt our dataset beforehand and store it in Azure storage; the CVM, upon startup, attests with Key Vault and obtains the key to decrypt the dataset inside the TEE. This demonstrates end-to-end confidentiality – the data is never seen unencrypted outside the VM.

    - Example use case: Imagine two companies want to do a joint ML project – one has sensitive training data, another has a proprietary model. Using SKR, each can provide their secrets (data encryption key, model encryption key) to a Key Vault that only releases them to a program running in a verified TEE. In fact we can describe it like this: one key can decrypt the model, another the data, and the inference or training happens with both secrets inside the enclave. Neither party's secret ever leaves the secure environment in plain form.

- **Azure Key Vault**: For our purposes, Key Vault Premium provides the SKR functionality. We will generate or upload a key to Key Vault that will be used to encrypt our dataset. The Key Vault will be configured with an SKR policy trusting our VM's attestation. When our code in the VM starts, it will call Key Vault (via a secure attested channel) to get the key. This process ensures the key only goes to our code if the environment is right.

## Step-by-Step: Deploying a Confidential VM via Azure CLI

We will use the Azure CLI to set up our confidential VM environment. This approach makes the tutorial easily reproducible for anyone with an Azure subscription and the appropriate permissions. Here's an outline of the steps we'll take:

### 1. Prerequisites & Setup

First, let's ensure you have the necessary tools and access rights.

> [!IMPORTANT]
> Azure Confidential VMs are not available on free trial accounts. You will need a pay-as-you-go subscription or an equivalent plan to proceed.

#### 1.1. Azure CLI Installation & Login

- **Install Azure CLI**: If you don't already have it, please [install the Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli). Confidential VM features require version 2.38.0 or newer. You can verify your installed version by running:
  ```powershell
  az --version`.
  ```

- **Log in to Azure**: Open your terminal and run the following command. A browser window will open, prompting you to sign in to your Azure account.
  ```powershell
  az login
  ```

#### 1.2. Verify Subscription and CVM Availability

- **Set Your Subscription**: If you manage multiple Azure subscriptions, make sure to select the one you intend to use for this tutorial.
  ```powershell
  # List your available subscriptions to find the correct one
  az account list --output table

  # Set the desired subscription by replacing "Your-Subscription-ID-or-Name"
  az account set --subscription "Your-Subscription-ID-or-Name"
  ```

- **Check CVM Availability**: Confidential VM instances are not available in all Azure regions, and access may depend on your subscription. We will use **West Europe** for this tutorial, a region where these features are commonly available. Supported VM series include:
    - **General Purpose**: DCasv5, DCesv5, DCadsv5, DCedsv5 series
    - **Memory Optimized**: ECasv5, ECesv5, ECadsv5, ECedsv5 series
    - **GPU Accelerated**: NCCadsH100v5 series

  Let's verify that the `Standard_DC2as_v5` size is available.
  ```powershell
  az vm list-skus --location westeurope --size Standard_DC2as_v5 --all --output table
  ```
  If the command returns a table with details for the VM size, you're ready to go. If you see a `ResourceType not found` error, your subscription may not have access to this VM family in West Europe. In that case, you might need to request access from Azure support or try a different region.

### 2. Create a Resource Group
          
In Azure, all resources must reside in a resource group, which serves as a logical container. Let's create one for this tutorial.

For convenience, we'll define variables for names that we will reuse.

```powershell
$RESOURCE_GROUP="MyConfidentialRG"
$LOCATION="westeurope"
```

Now, create the resource group. The command is the same for both shells.
```powershell
az group create --name $RESOURCE_GROUP --location $LOCATION
```

**Expected Output:**
The command will return a JSON object confirming that the resource group was created successfully. The `provisioningState` should be `Succeeded`.
```json
{
  "id": "/subscriptions/<your_subscription_id>/resourceGroups/MyConfidentialRG",
  "location": "westeurope",
  "managedBy": null,
  "name": "MyConfidentialRG",
  "properties": {
    "provisioningState": "Succeeded"
  },
  "tags": null,
  "type": "Microsoft.Resources/resourceGroups"
}
```

### 3. Secure Key Release set-up
For this tutorial, we will use the **Premium SKU of Azure Key Vault**. It provides the necessary Secure Key Release (SKR) functionality backed by FIPS 140-2 Level 2 validated HSMs and is significantly more cost-effective for learning and demonstration purposes.

> [!TIP]
> For storing and managing cryptographic keys in production, **Azure Managed HSM** is the recommended best practice. It offers a fully managed, highly available, single-tenant, standards-compliant HSM service. However, compared to Premium SKU of Azure Key Vault, it comes at a higher cost. If you are interested in using Managed HSM, please refer to the module [Secure Key Release set-up with Managed HSM](./Azure-Managed-HSM.md) (coming soon).

Azure offers two approaches for configuring release policies:

- **Default CVM Policy**: Azure provides a pre-configured policy that works with Microsoft's global attestation service. Here is the detail of this policy:
```json
{
    "version": "1.0.0",
    "anyOf": [
        {
            "authority": "https://sharedeus.eus.attest.azure.net/",
            "allOf": [
                {
                    "claim": "x-ms-attestation-type",
                    "equals": "sevsnpvm"
                },
                {
                    "claim": "x-ms-compliance-status",
                    "equals": "azure-compliant-cvm"
                }
            ]
        },
        {
            "authority": "https://sharedwus.wus.attest.azure.net/",
            "allOf": [
                {
                    "claim": "x-ms-attestation-type",
                    "equals": "sevsnpvm"
                },
                {
                    "claim": "x-ms-compliance-status",
                    "equals": "azure-compliant-cvm"
                }
            ]
        },
        {
            "authority": "https://sharedneu.neu.attest.azure.net/",
            "allOf": [
                {
                    "claim": "x-ms-attestation-type",
                    "equals": "sevsnpvm"
                },
                {
                    "claim": "x-ms-compliance-status",
                    "equals": "azure-compliant-cvm"
                }
            ]
        },
        {
            "authority": "https://sharedweu.weu.attest.azure.net/",
            "allOf": [
                {
                    "claim": "x-ms-attestation-type",
                    "equals": "sevsnpvm"
                },
                {
                    "claim": "x-ms-compliance-status",
                    "equals": "azure-compliant-cvm"
                }
            ]
        }
    ]
}
```
> [!NOTE]
> Here we see that the policy is defined to trust the attestation service in multiple Azure regions (i.e. East US, West US, North Europe or West Europe). This allows the key to be released to any Confidential VM running in those regions, as long as it meets the compliance criteria that are defined inside of the claims (i.e. `x-ms-attestation-type` and `x-ms-compliance-status`).

- **Custom Release Policy**: For more custom scenarios requiring specific compliance requirements or additional control, you can create your own custom release policy (see [Azure Key Vault secure key release policy grammar](https://learn.microsoft.com/en-us/azure/key-vault/keys/policy-grammar)). We will use this approach in this tutorial since we have a clear control on the claims that we want to ensure.

#### 3.1. Define Key Vault Name

Let's add a variable for our Key Vault's name. Note that Key Vault names must be **globally unique**. We'll append a random string to our chosen name to avoid conflicts.

```powershell

$KEY_VAULT_NAME="MyConfKV-$(Get-Random)"
```

#### 3.2. Create the Key Vault

Now, we'll create the Key Vault using the Premium SKU, which is required for SKR.

```powershell
az keyvault create `
  --name $KEY_VAULT_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --sku "Premium" `
  --enable-rbac-authorization true `
  --enable-purge-protection true
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

**Expected Output:**
The command will return a JSON object with details about the newly created Key Vault.
```json
 {
     "id": "/subscriptions/<your_subscription_id>/resourceGroups/MyConfidentialRG/providers/Microsoft.KeyVault/vaults/MyConfKV-<random>",
     "location": "westeurope",
     "name": "MyConfKV-<random>",
     "properties": {
         "enableRbacAuthorization": true,
         "provisioningState": "Succeeded",
         "sku": {
             "family": "A",
             "name": "Premium"
         },
         "tenantId": "<your-tenant-id>",
         "vaultUri": "https://myconfkv-<random>.vault.azure.net/"
     },
     "resourceGroup": "MyConfidentialRG",
     "systemData": {
         "createdAt": "<date-time-of-creation>",
         "createdBy": "<user@example.com>",
         "createdByType": "<User>",
         "lastModifiedAt": "<date-time-of-modification>",
         "lastModifiedBy": "<user@example.com>",
         "lastModifiedByType": "<User>"
     },
     "type": "Microsoft.KeyVault/vaults"
 }
```

#### 3.3. Assign Access Policy

Since the Key Vault is configured to use Azure RBAC for authorization, you must assign yourself a role to manage keys. We will assign the `Key Vault Crypto Officer` role, which provides the necessary permissions to create, manage, and use keys.

```powershell
$CURRENT_USER_ID = $(az ad signed-in-user show --query "id" -o tsv)
if (-not $CURRENT_USER_ID) {
    throw "Unable to retrieve user ID."
}
$KEY_VAULT_SCOPE = $(az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query "id" -o tsv)

az role assignment create `
  --role "Key Vault Crypto Officer" `
  --assignee-object-id $CURRENT_USER_ID `
  --assignee-principal-type "User" `
  --scope $KEY_VAULT_SCOPE
```

>[!NOTE]
> **Definition of the the parameters**:
> - `--role`: The role to assign, in this case, "Key Vault Crypto Officer".
> - `--assignee-object-id`: The object ID of the user or service principal to whom the role is assigned. This is obtained from the Azure AD signed-in user.
> - `--assignee-principal-type`: Specifies the type of principal (User, ServicePrincipal, etc.).
> - `--scope`: The scope at which the role is assigned, in this case we set it to the Key Vault we just created.

> [!WARNING]
> Role assignments can take a minute or two to propagate. If you immediately run the next command and get a permission error, wait a moment and try again.

#### 3.4. Create the release policy file

Before creating the KEK, we need to define its release-policy. The custom policy must include attestation requirements that match your VM's configuration. You can find an example here that will ensure that the environment is based on a SEV-SNP VM and that it is an 'Azure-compliant-CVM'. 

```json
{
  "version": "1.0.0",
  "anyOf": [
    {
      "authority": "https://sharedweu.weu.attest.azure.net",
      "allOf": [
        { "claim": "x-ms-isolation-tee.x-ms-attestation-type",  "equals": "sevsnpvm" },
        { "claim": "x-ms-isolation-tee.x-ms-compliance-status", "equals": "azure-compliant-cvm" }
      ]
    }
  ]
}
```

Save this content to a file named `release-policy.json` in your current working directory. Also, store the attestation authority URL for later use.

```powershell
$ATTEST_URL="https://sharedweu.weu.attest.azure.net"
```

> [!TIP]
> In this example, we are using the shared attestation authority for West Europe (`https://sharedweu.weu.attest.azure.net`). If you prefer to use your own dedicated attestation provider, you can follow the steps in [Provision a Dedicated Microsoft Azure Attestation Provider](../../modules/attestation/custom-attestation-provider.md) and replace the `authority` URL with your own attestation endpoint. Don't forget to also store the attestation URL in the `$ATTEST_URL` variable for later use.

#### 3.5 Create an Exportable Key with Release Policy

Let's define our key name:
```powershell

$KEK_NAME="KeyEncryptionKey"
```

Create the key:
```powershell
az keyvault key create `
  --vault-name $KEY_VAULT_NAME `
  --name $KEK_NAME `
  --kty RSA-HSM `
  --exportable true `
  --policy @release-policy.json
```

> [!NOTE]
> **Definition of the the parameters**:
> - `--vault-name`: The name of the Key Vault where the key will be stored.
> - `--name`: The name of the key to be created.
> - `--kty`: The key type, in this case, RSA-HSM (Hardware Security Module).
> - `--protection`: The kind of protection. In this case, it specifies that the key should be protected by an HSM.
> - `--exportable`: Indicates that the key can be exported from the Key Vault.
> - `--policy`: Uses the release policy that we defined in the file `release-policy.json`.

**Expected Output:**
The output will be a JSON object describing the key, including its unique identifier (`kid`). The key should show `"exportable": true` and include a release policy.

```json
{
  "attributes": {
    "created": "2025-07-28T14:30:00+00:00",
    "enabled": true,
    "exportable": true,
    "recoverableDays": 90,
    "recoveryLevel": "Recoverable+Purgeable",
    "updated": "2025-07-28T14:30:00+00:00"
  },
  "key": {
    "e": "AQAB",
    "keyOps": [
      "encrypt",
      "decrypt",
      "sign",
      "verify",
      "wrapKey",
      "unwrapKey"
    ],
    "kid": "https://myconfkv-<random>.vault.azure.net/keys/DataEncryptionKey/b8d8c0b6c6a04a8a9a4b1e0e1e0d8c0b",
    "kty": "RSA-HSM",
    "n": "..."
  },
  "managed": null,
  "tags": {},
  "releasePolicy": {
    "contentType": "application/json; charset=utf-8",
    "encodedPolicy": "..."
  }
}
```

#### 3.6. Verify the Release Policy Configuration

Let's verify that a release policy was correctly applied to the key. This confirms your key is configured for confidential computing.

```powershell
az keyvault key show `
  --vault-name $KEY_VAULT_NAME `
  --name $KEK_NAME `
  --query "releasePolicy" `
  -o json
```

You should see this output:
```powershell
{
  "contentType": "application/json; charset=utf-8",
  "encodedPolicy": "{\"version\":\"1.0.0\",\"anyOf\":[{\"authority\":\"https://sharedweu.weu.attest.azure.net\",\"allOf\":[{\"claim\":\"x-ms-isolation-tee.x-ms-attestation-type\",\"equals\":\"sevsnpvm\"},{\"claim\":\"x-ms-isolation-tee.x-ms-compliance-status\",\"equals\":\"azure-compliant-cvm\"}]}]}",
  "immutable": false
}
```

#### 3.7. Store the KEK identifiers for later use
```powershell
$keyJson  = az keyvault key show --vault-name $KEY_VAULT_NAME --name $KEK_NAME -o json | ConvertFrom-Json
$KEK_KID  = $keyJson.key.kid
$VAULT_ID = az keyvault show --name $KEY_VAULT_NAME --query id -o tsv
$KEK_RESOURCE  = "$VAULT_ID/keys/$KEK_NAME"
```

<b>Additional SKR Security Best Practices</b>

For production deployments, consider these additional security measures:

1. **Key Rotation**: Implement regular key rotation schedules.
2. **Audit Logging**: Enable Key Vault audit logs to monitor key access
3. **Network Isolation**: In production, use private endpoints and network restrictions

At this point, we have a Key Vault and a key ready for Secure Key Release. With this setup, your key has a comprehensive release policy that will only allow it to be released to a Confidential VM that can provide valid attestation evidence meeting all security requirements.

> [!TIP]
> Need OS-disk encryption with your own keys (CMK)? 
> Use the module: [OS Disk Encryption with Customer-Managed Keys (DES)](../../modules/os-disk-encryption/os-disk-encryption-cmk.md), then return here to continue deployment.


### 4. Deploy the Confidential VM

Now we are ready to create the Confidential VM itself. We will use the `az vm create` command with specific parameters to ensure it is a CVM.

A crucial step is to assign a **system-managed identity** to the VM. This identity is what the Model Training script inside of the CVM will use to securely authenticate with Azure Key Vault. We also need to grant this identity the correct permissions on our key.

First, let's create the VM. We use the variable we defined earlier for the resource group and we create new variables `VM_NAME`, `IMAGE` and `CVM_SIZE` to be used later:

```powershell
$VM_NAME = "MyCVM"
$IMAGE = "Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest"
$VM_SIZE = "Standard_DC2as_v5"
```
In the above, `Standard_DC2as_v5` is an example size (2 vCPUs, AMD SEV-SNP enabled) but feel free to choose a different size based on your requirements.
```powershell
az vm create `
  --resource-group $RESOURCE_GROUP `
  --name $VM_NAME `
  --image $IMAGE `
  --size $VM_SIZE `
  --security-type "ConfidentialVM" `
  --os-disk-security-encryption-type "DiskWithVMGuestState" `
  --enable-vtpm true `
  --enable-secure-boot true `
  --assign-identity [system] `
  --public-ip-sku Standard `
  --admin-username azureuser `
  --generate-ssh-keys
```


> [!NOTE]
> Explanation of each `az vm create` parameter:
>
> - `--resource-group $RESOURCE_GROUP`: The resource group we created earlier.
> - `--name $VM_NAME`: The name of the VM.
> - `--image $IMAGE`: Marketplace image/URN to deploy. For Confidential VMs, use a **CVM-qualified** Gen2 image such as
>   `Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest` so the OS meets confidential-computing requirements.
> - `--size $VM_SIZE`: VM SKU (e.g., `Standard_DC2as_v5`). Pick a size that supports Confidential VM (DC/EC v5 families, etc.).
> - `--security-type ConfidentialVM`: Provisions a **Confidential VM** (SEV-SNP/TDX-backed). Other options are `TrustedLaunch` or `Standard`, but those won’t enable the confidential features we need.
> - `--os-disk-security-encryption-type DiskWithVMGuestState`: Turns on **Confidential OS disk encryption** and protects the **VM Guest State**:
>   - If you **don’t** pass a Disk Encryption Set (DES), Azure uses **PMK** (platform-managed key) for the OS disk.
>   - If you also pass `--os-disk-secure-vm-disk-encryption-set $DES_ID`, Azure uses your **CMK** (customer-managed key in Key Vault) via the DES.
>   - Other accepted values:
>     - `VMGuestStateOnly` → no OS-disk pre-encryption; only guest state is protected (baseline you used earlier).
>     - `NonPersistedTPM` → Intel TDX-specific ephemeral TPM mode.
> - `--enable-vtpm true`: Attaches a **virtual TPM**. Required for confidential disk binding and for guest attestation evidence.
> - `--enable-secure-boot true`: Enables **UEFI Secure Boot** to harden the boot chain against tampering. Recommended for all Gen2 images.
> - `--assign-identity [system]`: Adds a **system-assigned managed identity** to the VM so code *inside* the guest can call Azure services (e.g., Key Vault SKR) with no secrets.
> - `--public-ip-sku Standard`: Allocates a Standard public IP (zonal, recommended). Basic is legacy in many regions.
> - `--admin-username azureuser`: Linux admin account created on the VM. `azureuser` is a conventional, safe default.
> - `--generate-ssh-keys`: Creates/uses local SSH keys and uploads the public key.


> [!IMPORTANT]
> Read through this section if you have set your Customer Managed Key for OS disk encryption (DES)
> 
> If you have set your Customer Managed Key (CMK) for OS disk encryption using a Disk Encryption Set (DES), you need to pass another parameter `--os-disk-secure-vm-disk-encryption-set $DES_ID` to the `az vm create` command. This parameter links the VM's OS disk encryption to your specified key in Key Vault:
>
> ```powershell
> az vm create `
>  --resource-group $RESOURCE_GROUP `
>  --name $VM_NAME `
>  --image $IMAGE `
>  --size $VM_SIZE `
>  --security-type "ConfidentialVM" `
>  --os-disk-security-encryption-type "DiskWithVMGuestState" `
>  --os-disk-secure-vm-disk-encryption-set $DES_ID `
>  --enable-vtpm true `
>  --enable-secure-boot true `
>  --assign-identity `
>  --public-ip-sku Standard `
>  --admin-username azureuser `
>  --generate-ssh-keys
> ```
> Make sure to replace `$DES_ID` with the actual resource ID of your Disk Encryption Set

The command will output the VM's details when done.
```powershell
{
  "fqdns": "",
  "id": "/subscriptions/<your_subscription_id>/resourceGroups/MyConfidentialRG/providers/Microsoft.Compute/virtualMachines/MyCVM",
  "identity": {
    "systemAssignedIdentity": "<sytem_assigned_id>",
    "userAssignedIdentities": {}
  },
  "location": "westeurope",
  "macAddress": "<mac_address>",
  "powerState": "VM running",
  "privateIpAddress": "10.0.0.4",
  "publicIpAddress": "<public_ip_address>",
  "resourceGroup": "MyConfidentialRG"
}
```

After the VM is created, we need to authorize its new managed identity to release our key.

1.  **Get the Principal ID**: We fetch the `principalId` of the VM's new system-assigned identity.
    ```powershell
    
    $VM_PRINCIPAL_ID = az vm show -d `
      --resource-group $RESOURCE_GROUP `
      --name $VM_NAME `
      --query "identity.principalId" `
      -o tsv
    ```

2.  **Assign Role to VM Identity**: We grant the VM's identity the `Key Vault Crypto Service Release User` role. This role is composed of the `release` permission required for SKR. This is the final link in the chain: only this specific VM identity will be authorized to release the KEK stored inside of the Key Vault.
    ```powershell
    az role assignment create `
      --role "Key Vault Crypto Service Release User" `
      --assignee-object-id $VM_PRINCIPAL_ID `
      --assignee-principal-type ServicePrincipal `
      --scope $KEK_RESOURCE
    ```

**Result**: We have a running Confidential VM that is now authorized to securely retrieve our decryption key. Azure ensures this VM's memory is encrypted with a unique hardware key. When it booted, it performed remote attestation – we could use Azure Attestation Service to get a report if we wanted, but Azure also makes the attestation evidence available to Key Vault for SKR.

### 5. Prepare and Encrypt the Dataset Locally

Now comes the exciting part - let's prepare some data for our confidential machine learning demonstration! 

For this tutorial, we'll be working with a sample diabetes prediction dataset (sourced from [Kaggle's Diabetes Data Set](https://www.kaggle.com/datasets/mathchi/diabetes-data-set)). While this is fictional data, imagine it represents highly sensitive medical records that require the utmost protection. We've chosen to demonstrate a diabetes prediction task using XGBoost, a popular machine learning algorithm - though the same principles apply to any ML workload you might want to run on confidential data.

The beauty of this setup is that we'll implement **end-to-end encryption**: your sensitive data never exists in plain text outside of a Trusted Execution Environment (TEE). This means that even Azure itself cannot peek at your data during processing.

To make this happen, we'll use a powerful security pattern that separates the key used for the data from the key that protects it. Here's how it works:

First, we'll locally generate a strong symmetric key called a **Data Encryption Key (DEK)**. This is a fast, single-use key whose only job is to encrypt our large CSV file.

But we can't just send this key to the cloud in plaintext. Instead, we'll use the powerful, HSM-protected key we created in Azure Key Vault. This key acts as a **Key Encryption Key (KEK)**. We'll ask Key Vault to use our KEK to encrypt—or **"wrap"**—the DEK.

The result is a small, safely encrypted version of our DEK. It can only be unwrapped inside a trusted Confidential VM that proves its identity to Key Vault.

Here's our secure workflow for this section:
1.  **Generate a DEK** locally on your machine.
2.  **Encrypt the dataset** with this DEK using the fast and secure `AES-256-GCM` algorithm.
3.  **"Wrap" the DEK** with our KEK.
4.  **Upload the artifacts** (the encrypted dataset and the newly wrapped DEK) to our Confidential VM.

This approach ensures that the raw `confidentialData.csv` is never exposed to the cloud provider or any intermediate systems - pretty neat, right?

#### 5.1. Prerequisites
In our tutorial, we are writing our helpers in python, but feel free to choose any programming language that would suits best your needs.

##### 5.1.1. Install Local Python Dependencies
Ensure that you have a python-env setted and install the required librairies
```powershell
pip install azure-identity azure-keyvault-keys cryptography
```

##### 5.1.2. Locate your dataset
The dataset that we will be using for this tutorial can be found on [Kaggle](https://www.kaggle.com/datasets/mathchi/diabetes-data-set) and is structured like this:
```shell
RangeIndex: 768 entries, 0 to 767
Data columns (total 9 columns):
 #   Column                    Non-Null Count  Dtype
---  ------                    --------------  -----
 0   Pregnancies               768 non-null    int64
 1   Glucose                   768 non-null    int64
 2   BloodPressure             768 non-null    int64
 3   SkinThickness             768 non-null    int64
 4   Insulin                   768 non-null    int64
 5   BMI                       768 non-null    float64
 6   DiabetesPedigreeFunction  768 non-null    float64
 7   Age                       768 non-null    int64
 8   Outcome                   768 non-null    int64
dtypes: float64(2), int64(7)
memory usage: 54.1 KB
```

Our goal is to create a Model that would be able to detect if a patient has diabete ("Outcome" column), based on all of the observations ("Pregnancies", "Glucose", "BloodPressure", "SkinThickness", "Insulin", "BMI", "DiabetesPedigreeFunction" and "Age").

You can reproduce our full tutorial by downloading the data with Kaggle CLI (or any other method):
```powershell
kaggle datasets download mathchi/diabetes-data-set
```

In our case, we will store this data inside of a `data` directory under the name `confidentialData.csv`.

#### 5.2. Create the Encryption Script

Let's start by setting up our encryption workflow on your local machine. We'll create a Python script called `encrypt_data.py` that will securely encrypt our diabetes dataset using a sophisticated hybrid encryption approach.

This script will connect to your Azure Key Vault, use the public part of your HSM-protected key to encrypt the `confidentialData.csv` file, and save the result as `confidentialData.enc` along with its corresponding wrapped DEK inside of `confidentialData.key`. Think of it as creating a digitally sealed envelope that only a genuine Confidential VM can open!

The script is already created for you. Here's how it works:

```python
import sys
import os
import logging
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, KeyWrapAlgorithm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

CHUNK_SIZE = 8 * 1024 * 1024

def encrypt_file(src_path, dek):
    nonce = os.urandom(12)
    encryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce)).encryptor()
    enc_path = src_path.with_suffix(".enc")
    with src_path.open("rb") as fin, enc_path.open("wb") as fout:
        fout.write(nonce)
        while True:
            chunk = fin.read(CHUNK_SIZE)
            if not chunk: break
            fout.write(encryptor.update(chunk))
        fout.write(encryptor.finalize())
        fout.write(encryptor.tag)
    return enc_path

def main():
    if len(sys.argv) != 4:
        logging.error("Usage: python encrypt_data.py <FILE> <VAULT_NAME> <KEY_NAME>")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    vault_name, key_name = sys.argv[2], sys.argv[3]

    logging.info(f"Starting encryption for: {src_path.name}")
    
    # Authenticate and get a crypto client for our KEK
    kv_uri = f"https://{vault_name}.vault.azure.net"
    credential = DefaultAzureCredential()
    crypto_client = CryptographyClient(f"{kv_uri}/keys/{key_name}", credential)

    # 1. Generate a random 32-byte Data Encryption Key (DEK)
    dek = os.urandom(32)

    # 2. Encrypt the local file with the DEK using AES-256-GCM
    encrypted_file_path = encrypt_file(src_path, dek)
    logging.info(f"Successfully encrypted data to '{encrypted_file_path.name}'")

    # 3. Wrap the DEK with the KEK in Azure Key Vault
    logging.info(f"Wrapping DEK with KEK '{key_name}' using rsa1_5 for compatibility...")
    wrap_result = crypto_client.wrap_key(KeyWrapAlgorithm.rsa1_5, dek)
    wrapped_dek = wrap_result.encrypted_key
    
    key_file_path = src_path.with_suffix(".key")
    key_file_path.write_bytes(wrapped_dek)
    logging.info(f"Saved wrapped DEK to '{key_file_path.name}'")
    
    del dek # Securely delete the DEK from memory
    logging.info("Encryption process complete.")

if __name__ == "__main__":
    main()
```

You can now use the script like this:

```powershell
python encrypt_data.py "data/confidentialData.csv" $KEY_VAULT_NAME $KEK_NAME
```

You should be able to see this output:
```output
2025-01-XX XX:XX:XX - INFO - Starting encryption for: confidentialData.csv
2025-01-XX XX:XX:XX - INFO - Successfully encrypted data to 'confidentialData.enc'
2025-01-XX XX:XX:XX - INFO - Wrapping DEK with KEK 'KeyEncryptionKey' using rsa1_5 for compatibility...
2025-01-XX XX:XX:XX - INFO - Saved wrapped DEK to 'confidentialData.key'
2025-01-XX XX:XX:XX - INFO - Encryption process complete.
```

Perfect! You should now have 2 new file, `confidentialData.enc` and `confidentialData.key`, in your `data` directory. This encrypted package is what we'll upload to the CVM in the next steps - it's completely safe to transfer since only a genuine Confidential VM with proper attestation can decrypt it.

#### 5.3. Create the CVM's Machine Learning Script

Now, let's take a look at the star of our show - the Python script that will run *inside* of the Confidential VM! This script, `train_xgb.py`, is where the magic happens. It's essentially a secure version of our original machine learning workflow, enhanced with confidential computing capabilities.

Here's what this clever script does:
1.  **Authenticates to Azure Key Vault** using the CVM's **Managed Identity** (no passwords or secrets needed!)
2.  **Unwraps the Symmetric Key**: Reads our encrypted package, sends the "wrapped" symmetric key to Key Vault for attestation, and receives back the decrypted key if everything checks out
3.  **Processes the data securely**: Decrypts the diabetes dataset in memory and trains an XGBoost model to predict diabetes outcomes

The beauty is that all of this happens within the secure confines of the Trusted Execution Environment, ensuring your sensitive medical data remains protected throughout the entire ML pipeline.

We first need to write a the module that will be responsible of the decyphering of the DEK by releasing our KEK from the Key Vault. We will call this module [skr_decrypt.py](src/skr_decrypt.py) and here is its content:

```python
import os
import base64
import subprocess
import io
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def unwrap_dek(wrapped_key_path: str, attest_url: str, key_kid: str) -> bytes:
    """Uses the AzureAttestSKR tool to decrypt the DEK inside the TEE."""
    with open(wrapped_key_path, "rb") as f:
        wrapped_b64 = base64.b64encode(f.read()).decode("ascii")

    # Command for calling the AzureAttestSKR tool from the 
    # azure repo https://github.com/Azure/confidential-computing-cvm-guest-attestation/tree/main/cvm-securekey-release-app
    # We are using sudo since this tool needs to communicate directly 
    # with the virtual Trusted Platform Module device inside the VM to get a
    # cryptographically signed report that proves the VM's identity and posture.

    cmd = [
        "sudo", "-E", os.path.expanduser("~/AzureAttestSKR"),
        "-a", attest_url,
        "-k", key_kid,
        "-c", "imds",
        "-s", wrapped_b64, "-u"
    ]

    res = subprocess.run(cmd, capture_output=True, check=True)
    dek = res.stdout

    if dek.endswith(b"\n"):
        dek = dek[:-1]

    if len(dek) != 32:
        raise RuntimeError(f"DEK length is {len(dek)} bytes, expected 32. Stderr: {res.stderr.decode()}")

    return dek

def decrypt_to_memory(enc_path: str, dek: bytes) -> io.BytesIO:
    """
    Decrypts an AES-GCM file and returns its content as an
    in-memory io.BytesIO object.
    """
    with open(enc_path, "rb") as f:
        # The file structure is: [12-byte nonce][ciphertext][16-byte tag]
        nonce = f.read(12)
        f.seek(-16, os.SEEK_END)
        tag = f.read(16)

        # The ciphertext is everything between the nonce and the tag
        f.seek(12)
        ciphertext = f.read(os.path.getsize(enc_path) - 12 - 16)

    decryptor = Cipher(algorithms.AES(dek), modes.GCM(nonce, tag)).decryptor()

    plaintext = decryptor.update(ciphertext) + decryptor.finalize()

    # Return the decrypted data in a binary memory buffer
    return io.BytesIO(plaintext)

# The decrypt_to_file function is kept in case you need it for other purposes
def decrypt_to_file(enc_path: str, out_path: str, dek: bytes):
    """Decrypts data to a file (the previous method)."""
    plaintext_stream = decrypt_to_memory(enc_path, dek)
    with open(out_path, "wb") as f:
        f.write(plaintext_stream.getbuffer())
```

Once we have a script that can securely decrypt the dataset, we can use it in our training pipeline. For this tutorial, we've written a very simple machine learning classifier training script based on [XGBoost](https://xgboost.readthedocs.io/en/stable/) in [train_xgb.py](src/train_xgb.py). Here is its content:
```python
import os
import pandas as pd
import logging
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb
import skr_decrypt as skr

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def main():
    load_dotenv()
    logging.info("--- Starting Confidential XGBoost Training (In-Memory) ---")

    # 1. Securely unwrap the DEK inside the TEE
    logging.info("Attesting to Azure and unwrapping DEK...")
    dek = skr.unwrap_dek(
        os.environ["WRAPPED_KEY_FILE"],
        os.environ["ATTEST_URL"],
        os.environ["KEY_KID"]
    )
    logging.info("DEK securely retrieved.")

    # 2. Decrypt the dataset directly into memory
    encrypted_file = os.environ['ENC_FILE']
    logging.info(f"Decrypting '{encrypted_file}' into memory...")
    decrypted_stream = skr.decrypt_to_memory(encrypted_file, dek)
    del dek # The DEK is no longer needed, clear it from memory
    logging.info("Decryption complete.")

    # 3. Load data and train the model
    logging.info("Loading data into pandas and training model...")
    df = pd.read_csv(decrypted_stream)
    
    X = df.drop("Outcome", axis=1)
    y = df["Outcome"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBClassifier(eval_metric='logloss')
    model.fit(X_train, y_train)
    logging.info("Model training finished.")

    # 4. Evaluate the model
    logging.info("Evaluating model performance...")
    preds = model.predict(X_test)
    acc = accuracy_score(y_test, preds)
    report = classification_report(y_test, preds)

    logging.info("--- Training Complete ---")
    logging.info(f"Model Accuracy: {acc:.4f}")
    # Log the multi-line classification report
    logging.info(f"Classification Report:\n{report}")

if __name__ == "__main__":
    main()
```

### 6. Connect to the VM and Transfer Files

With the VM running and authorized, the next step is to connect to it and upload the files needed for our confidential ML task.

#### 6.1. Get the VM's Public IP Address

Retrieve the public IP address of your new VM.

```powershell

$VM_PUBLIC_IP=$(az vm show -d --name $VM_NAME --resource-group $RESOURCE_GROUP --query "publicIps" -o tsv)
```

#### 6.2. Create a `.env` file for the CVM

In order to transfer smoothly the environment variables that the CVM will need to have access to, the best is to create a `.env` file and transfer it to the cvm via `scp`.
```powershell
@"
KEY_VAULT_NAME=$KEY_VAULT_NAME
KEK_NAME=$KEK_NAME
KEY_KID=$KEK_KID
ATTEST_URL=$ATTEST_URL
ENC_FILE=confidentialData.enc
WRAPPED_KEY_FILE=confidentialData.key
"@ | Out-File -FilePath .\.env -Encoding ASCII
```

#### 6.3. Upload the Scripts and Encrypted Data

From your local machine's `explore` directory, use `scp` (Secure Copy Protocol) to upload the Python script and the encrypted dataset to the VM's home directory.

```powershell
scp .\train_xgb.py .\skr_decrypt.py .\data\confidentialData.enc .\data\confidentialData.key .\.env azureuser@${VM_PUBLIC_IP}:~
```
> [!NOTE]
> If you are using Windows and don't have `scp` in your path, you can use the `scp.exe` included with modern versions of Windows or install a tool like Git Bash. You may be prompted to accept the VM's host key on the first connection.

#### 6.4. Connect via SSH

Now, connect to the VM using SSH. Since we used `--generate-ssh-keys`, your default SSH key will be used for authentication.

```powershell
ssh azureuser@$VM_PUBLIC_IP
```
You are now connected to the shell of your Confidential VM. The environment inside the VM looks like a standard Ubuntu server, but with the crucial difference that it has a virtual TPM and its memory is encrypted.

### 7. Configure the CVM Environment

In order to make the CVM able to decypher the data in its TEE to perform SKR, we first need to set up the guest attestation environment. Guest attestation is the in-VM proof that your machine is a genuine, hardware-attested Confidential VM with the expected security posture (vTPM, Secure Boot, measurements), verified by Microsoft Azure Attestation before you trust it. We install the [Azure/confidential-computing-cvm-guest-attestation](https://github.com/Azure/confidential-computing-cvm-guest-attestation) repo so we can use its sample tools (e.g., `AzureAttestSKR`) to gather that evidence and gate Key Vault Secure Key Release on successful attestation.


#### 7.1. Update and Install build tools and librairies
```bash
sudo apt-get update && sudo apt-get install -y \
  build-essential cmake git libssl-dev libcurl4-openssl-dev \
  libjsoncpp-dev libboost-all-dev nlohmann-json3-dev python3-pip
```

#### 7.2. Install the Azure Guest Attestation Library
You can download and install the latest version of the Azure Guest Attestation library directly from [Microsoft's package repository](https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/). This library provides the necessary tools to perform attestation and interact with the TPM.

```bash
wget https://packages.microsoft.com/repos/azurecore/pool/main/a/azguestattestation1/azguestattestation1_1.1.2_amd64.deb 
sudo dpkg -i azguestattestation1_1.1.2_amd64.deb 
rm azguestattestation1_1.1.2_amd64.deb 
```

#### 7.3. Add user to 'tss' group to access the TPM device
```bash
sudo usermod -a -G tss $USER
```

#### 7.4. Clone and build the official Azure SKR sample tool
Clone and build the [sample secure key release app](https://github.com/Azure/confidential-computing-cvm-guest-attestation/tree/main/cvm-securekey-release-app). This app has been developped under the official Azure [confidential-computing-cvm-guest-attestation](https://github.com/Azure/confidential-computing-cvm-guest-attestation/tree/main).

```bash
git clone https://github.com/Azure/confidential-computing-cvm-guest-attestation.git
cd confidential-computing-cvm-guest-attestation/cvm-securekey-release-app
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j"$(nproc)"
cp AzureAttestSKR ~/
cd ~
```

> [!TIP]
> By default, the `AzureAttestSKR` will not have any `SKR_TRACE_ON` set, so it will not output any debug information. If you want to enable debug logging, you can set the environment variable `SKR_TRACE_ON=1` to either `1` (minimal logs) or `2` (detailed logs) before running the script.
> ```bash
> export SKR_TRACE_ON=1
> ```
> It is however recommended to not enable this in production environments, as it may expose sensitive information.

#### 7.5. Install the Python Librairies
```bash
pip3 install pandas scikit-learn xgboost cryptography python-dotenv
```

### 8. Execute the Confidential ML Task Inside the VM

Once we our CVM's environment is set up, we can run our ML script. It will securely retrieve the key, decrypt the data in memory, and train the model.

```bash
# Inside the VM's SSH session
python3 train_xgb.py
```

**Expected Output:**
The script will now run directly, as the libraries are already installed. The output demonstrates the entire confidential workflow: authenticating via managed identity, triggering attestation to unwrap the key, decrypting the data, and finally, evaluating the model.

```
2025-01-XX XX:XX:XX - INFO - --- Starting Confidential XGBoost Training (In-Memory) ---
2025-01-XX XX:XX:XX - INFO - Attesting to Azure and unwrapping DEK...
2025-01-XX XX:XX:XX - INFO - DEK securely retrieved.
2025-01-XX XX:XX:XX - INFO - Decrypting 'confidentialData.enc' into memory...
2025-01-XX XX:XX:XX - INFO - Decryption complete.
2025-01-XX XX:XX:XX - INFO - Loading data into pandas and training model...
2025-01-XX XX:XX:XX - INFO - Model training finished.
2025-01-XX XX:XX:XX - INFO - Evaluating model performance...
2025-01-XX XX:XX:XX - INFO - --- Training Complete ---
2025-01-XX XX:XX:XX - INFO - Model Accuracy: 0.7208
2025-01-XX XX:XX:XX - INFO - Classification Report:
              precision    recall  f1-score   support

           0       0.82      0.73      0.77        99
           1       0.59      0.71      0.64        55

    accuracy                           0.72       154
   macro avg       0.70      0.72      0.71       154
weighted avg       0.74      0.72      0.73       154
```

**Success!** You have just run a machine learning workload on encrypted data inside a Confidential VM. The data was only ever in plaintext within the hardware-protected memory of the CVM, demonstrating a true end-to-end confidential workflow.

### 9. Cleanup

To avoid incurring further costs once everything is done, you should delete the resources you created. The easiest way to do this is to delete the entire resource group.

```powershell
az group delete --name $RESOURCE_GROUP --yes --no-wait
```
> [!WARNING]
> This command will permanently delete the resource group and all resources within it, including the VM, Key Vault, and Attestation provider.

Alternatively, if you want to keep some resources and only delete specific ones:

```powershell
az vm delete --resource-group $RESOURCE_GROUP --name $VM_NAME --yes
az keyvault delete --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP
az attestation delete --name $ATTESTATION_PROVIDER --resource-group $RESOURCE_GROUP
```
