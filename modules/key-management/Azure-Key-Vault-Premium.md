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

---

## Exports (available after this module)

```powershell
$KEY_VAULT_NAME
$VAULT_ID
$KEY_VAULT_URI
```

> \[!TIP]
> If you prefer **Managed HSM** for production-grade isolation, use the alternative module
> `modules/key-management/Managed-HSM.md` *(coming soon)*, then follow the same policy/key steps in your tutorial with MHSM switches (`--hsm-name`).

---

## Continue your tutorial

After completing this module, jump back to policy authoring in your tutorial of choice:

| Tutorial                                                 | Continue at                                                    |
| -------------------------------------------------------- | -------------------------------------------------------------- |
| **Confidential ML Training (CPU)**                       | [3.4. Create the release policy file](../../tutorials/confidential-ml-training/README.md#34)                           |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [4.3. Definition of the release policy](../../tutorials/confidential-llm-inferencing/README.md#43)                           |
