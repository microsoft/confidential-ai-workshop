# Provision Azure Key Vault (Premium) for Secure Key Release (SKR)

## Overview

Use this module to create and prepare an **Azure Key Vault (Premium)** for Secure Key Release (SKR). It is reusable across tutorials (training on CPU, LLM inferencing on GPU, and Whisper pipeline). Even if your tutorials include an inline AKV setup, this module provides a clean, standalone path you can reference when needed.

## Prerequisites

* Azure CLI installed and logged in (`az login`).
* Permissions to create Key Vaults and assign **Azure RBAC** roles.
* The following environment variables:
```powershell
$RESOURCE_GROUP
$LOCATION
```

---

## Procedure

> \[!NOTE]
> If your subscription is brand new, register the resource provider first and wait until it shows **Registered**:
>
> ```powershell
> az provider register --namespace Microsoft.KeyVault
> az provider show --namespace Microsoft.KeyVault --query "registrationState"
> ```

### 1) Create the Key Vault (Premium) with RBAC and purge protection

First, we need to give to our AKV a name:
```powerhsell
$KEY_VAULT_NAME = "MyConfKV-$(Get-Random)"
```

Then we can create it with this command:
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
> * `--enable-rbac-authorization true`: Switches the Key Vault **data plane** (keys/secrets/certs) to **[Azure RBAC](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview)**. You’ll manage access with roles like *Key Vault Crypto Officer* / *Key Vault Administrator* instead of access policies. This is what enables the SKR-specific “Crypto Service” roles used by DES/CMK flows.
>
> * `--enable-purge-protection true`: Prevents **permanent deletion** (purge) of the vault and its objects during the soft-delete retention period **even by privileged users**. It’s a strong safety net for production, but note it **can’t be disabled** once turned on and may slow teardown in demo environments.

**Expected Output (trimmed):**

```json
{
  "id": "/subscriptions/<sub>/resourceGroups/MyConfidentialRG/providers/Microsoft.KeyVault/vaults/MyConfKV-<random>",
  "location": "westeurope",
  "name": "MyConfKV-<random>",
  "properties": {
    "enableRbacAuthorization": true,
    "provisioningState": "Succeeded",
    "sku": { "family": "A", "name": "Premium" },
    "vaultUri": "https://myconfkv-<random>.vault.azure.net/"
  },
  "type": "Microsoft.KeyVault/vaults"
}
```

### 2) Assign yourself RBAC to manage keys

Use the **Key Vault Crypto Officer** role (sufficient for key creation and usage). Propagation can take up to a couple of minutes.

```powershell
$CURRENT_USER_ID = az ad signed-in-user show --query id -o tsv
$KEY_VAULT_SCOPE = az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query id -o tsv

az role assignment create `
  --role "Key Vault Crypto Officer" `
  --assignee-object-id $CURRENT_USER_ID `
  --assignee-principal-type User `
  --scope $KEY_VAULT_SCOPE
```

> \[!WARNING]
> If the next commands fail with permission errors, wait 60–120 seconds and try again (RBAC propagation delay).

### 3) Capture identifiers for reuse

```powershell
$VAULT_ID = az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query id -o tsv
$KEY_VAULT_URI = az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP --query properties.vaultUri -o tsv
```

### 4) (Optional) Quick validation

```powershell
az keyvault show --name $KEY_VAULT_NAME --resource-group $RESOURCE_GROUP -o table
```

### 5) Author the SKR release policy

Create **Release Policy** in a json file named `release_policy.json` with claims that match your attestation flow. Example (SEV‑SNP CVM, shared West Europe MAA):

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

### 6) Create an exportable KEK with the release policy

```powershell
az keyvault key create `
  --vault-name $KEY_VAULT_NAME `
  --name $KEK_NAME `
  --kty RSA-HSM `
  --exportable true `
  --policy @release_policy.json
```

You can now verify that the policy was applied:

```powershell
az keyvault key show `
  --vault-name $KEY_VAULT_NAME `
  --name $KEK_NAME `
  --query "releasePolicy" -o json
```

Moreover, you can store its identifiers for reuse:

```powershell
$keyJson = az keyvault key show --vault-name $KEY_VAULT_NAME --name $KEK_NAME -o json | ConvertFrom-Json
$KEK_KID = $keyJson.key.kid
$KEK_RESOURCE = "$VAULT_ID/keys/$KEK_NAME"
```


### 7) (Optional) OS‑disk encryption with CMK

If you plan to use this key for OS-disk encryption with Customer-Managed Keys (CMK) in a Disk Encryption Set (DES), you can follow the steps in the [OS Disk Encryption with CMK backed by Azure Key Vault Premium](../os-disk-encryption/os-disk-encryption-cmk.md) module using the AKV that you created by following the previous steps (use `$KEY_VAULT_NAME` and `$VAULT_ID`).

---

## Exports (available after this module)

Key Vault details for reuse:

```powershell
$KEY_VAULT_NAME
$KEY_VAULT_URI
$VAULT_ID
```

Key details for reuse:

```powershell
$KEK_NAME
$KEK_KID
$KEK_RESOURCE
```

## Continue your tutorial

After completing this module, jump back to the Confidential VM deployment in your tutorial of choice:

| Tutorial                                                 | Continue at                                                                                                                            |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Confidential ML Training (CPU)**                       | [4. Deploy the Confidential VM](../../tutorials/confidential-ml-training/README.md#4-deploy-the-confidential-vm)                       |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [5. Deploy the Confidential GPU VM](../../tutorials/confidential-llm-inferencing/README.md#5-deploy-the-confidential-gpu-vm) |


