# Configure OS Disk Encryption with Customer‑Managed Keys backed by Azure Key Vault (Premium)

## Overview

Use this module to set up OS disk encryption for Confidential VMs with your own keys by creating and wiring a **Disk Encryption Set (DES)**.

## Prerequisites

* Azure CLI installed and logged in (`az login`).
* PowerShell with `Microsoft.Graph` module available (for service principal registration).
* Sufficient permissions to create Entra ID applications/service principals, assign RBAC roles, and manage Key Vault keys.
* Existing objects used by your tutorial environment (example below):

  ```powershell
  $RESOURCE_GROUP = "MyConfidentialRG"
  $KEY_VAULT_NAME = "MyConfidentialKV"
  $VAULT_ID = "/subscriptions/<subId>/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.KeyVault/vaults/$KEY_VAULT_NAME"
  ```

> [!TIP]
> If you haven’t created your Azure Key Vault (Premium) yet, run the module [Provision Azure Key Vault (Premium)](../key-management/Azure-Key-Vault-Premium.md) and export `$KEY_VAULT_NAME` / `$VAULT_ID` first.

## Procedure

### 1. Register the Confidential VM Orchestrator Service Principal

To enable advanced capabilities like OS disk encryption with your own keys, you must register the "Confidential VM Orchestrator" service principal in your Azure tenant. This is a one-time setup task.

**Connect to Microsoft Graph**: Open a PowerShell terminal to run the following commands. You'll need the `Microsoft.Graph` module. If it's not installed, run `Install-Module Microsoft.Graph -Scope CurrentUser` to add it.

  ```powershell
  # Replace "your-tenant-id" with your actual Azure Tenant ID
  Connect-MgGraph -TenantId "your-tenant-id" -Scopes "Application.ReadWrite.All"

  # Create the service principal
  New-MgServicePrincipal -AppId "bf7b6499-ff71-4aa2-97a4-f372087be7f0" -DisplayName "Confidential VM Orchestrator"
  ```

Grab its objectId for role assignment (RBAC)

```powershell
$CVM_ORCH_SP_ID = az ad sp show --id "bf7b6499-ff71-4aa2-97a4-f372087be7f0" --query id -o tsv
```

### 2. Create a Key for Disk Encryption using your created Key Vault

Now that you have registered the Confidential VM Orchestrator, you can create a key in your Key Vault to be used for OS disk encryption.

Create the key name:

```powershell
$OS_KEY_NAME = "OsDiskKey"

# Create an RSA-HSM key with the standard Confidential VM release policy
az keyvault key create `
  --vault-name $KEY_VAULT_NAME `
  --name $OS_KEY_NAME `
  --kty RSA-HSM `
  --exportable true `
  --default-cvm-policy
```

Store its identifiers:

```powershell
$osKeyJson = az keyvault key show --vault-name $KEY_VAULT_NAME --name $OS_KEY_NAME -o json | ConvertFrom-Json
$OS_KEY_KID = $osKeyJson.key.kid
$OS_KEY_RES = "$VAULT_ID/keys/$OS_KEY_NAME"
```

### 3. Create a Disk Encryption Set (DES) that points to the OS-disk key

```powershell
$DES_NAME = "MyCvmOsDiskDES"

az disk-encryption-set create `
  --resource-group $RESOURCE_GROUP `
  --name $DES_NAME `
  --key-url $OS_KEY_KID `
  --encryption-type ConfidentialVmEncryptedWithCustomerKey
```

Get the DES identity and resource id:

```powershell
$DES_PRINCIPAL_ID = az disk-encryption-set show -g $RESOURCE_GROUP -n $DES_NAME --query identity.principalId -o tsv
$DES_ID = az disk-encryption-set show -g $RESOURCE_GROUP -n $DES_NAME --query id -o tsv
```

### 4. RBAC assignments

**DES managed identity → Encryption role on the OS-disk key**

```powershell
az role assignment create `
  --role "Key Vault Crypto Service Encryption User" `
  --assignee-object-id $DES_PRINCIPAL_ID `
  --assignee-principal-type ServicePrincipal `
  --scope $OS_KEY_RES
```

**Confidential VM Orchestrator SP → Release role on the OS-disk key**

```powershell
az role assignment create `
  --role "Key Vault Crypto Service Release User" `
  --assignee-object-id $CVM_ORCH_SP_ID `
  --assignee-principal-type ServicePrincipal `
  --scope $OS_KEY_RES
```

> These two RBAC roles map to the access-policy permissions wrapKey/unwrapKey/get for DES, and get/release for the orchestrator.

---

## Continue your tutorial

| Tutorial                               | Continue at                                                                                                                            |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Confidential ML Training (CPU)**     | [4. Deploy the Confidential VM](../../tutorials/confidential-ml-training/README.md#4-deploy-the-confidential-vm)                       |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [5. Deploy the Confidential GPU VM](../../tutorials/confidential-llm-inferencing/README.md#5-deploy-the-confidential-gpu-vm) |
