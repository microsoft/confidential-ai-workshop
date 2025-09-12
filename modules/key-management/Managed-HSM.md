# Provision Azure Managed HSM for Secure Key Release (SKR)

## Overview

Use this module to provision and activate an [Azure Key Vault Managed HSM](https://learn.microsoft.com/en-us/azure/key-vault/managed-hsm/overview) and prepare it for [Secure Key Release (SKR)](https://learn.microsoft.com/en-us/azure/confidential-computing/concept-skr-attestation). Choose Managed HSM when you need single‑tenant isolation and **FIPS 140‑3 Level 3** validated HSMs. This module is reusable across tutorials (CPU training, GPU LLM inferencing).

## Prerequisites

* Azure CLI installed and logged in (`az login`).
* Permissions to create Managed HSM and assign **Managed HSM local RBAC** roles.
* OpenSSL available (for generating activation certificates).
* A resource group and region prepared, for example:

```powershell
$RESOURCE_GROUP = "MyConfidentialRG"
$LOCATION = "westeurope"
```
---

## Procedure

### 1) Create and provision the Managed HSM

First, define the HSM name and create it with initial administrators.

```powershell
$HSM_NAME = "MyMHSM-$(Get-Random)"
```

Then, create the HSM and set initial **administrators** (local RBAC). Use the currently signed‑in user or a list of object IDs.

```powershell
$CURRENT_USER_ID = az ad signed-in-user show --query id -o tsv

az keyvault create `
  --hsm-name $HSM_NAME `
  --resource-group $RESOURCE_GROUP `
  --location $LOCATION `
  --administrators $CURRENT_USER_ID `
  --retention-days 7
  # optionally add: --enable-purge-protection true
```

> \[!NOTE]
> * `--administrators`: Comma‑separated **object IDs** that become the initial local RBAC admins for the HSM (they can activate the HSM and manage local RBAC).
>
> * `--retention-days`: Soft‑delete retention for the HSM. The HSM remains billable until it is purged after this period.
>
> * `--enable-purge-protection true` (optional): Prevents permanent deletion during the retention window—even by privileged users. Once enabled, it cannot be turned off.
>
> Managed HSM always uses **local RBAC** for the data plane (there is no `--enable-rbac-authorization` switch like Key Vault).

> [!NOTE]
> The creation can take several minutes. The HSM is created in a **provisioning state**. You must activate it before using it for key management. 

**Expected Output:**

```json
{
  "name": "MyMHSM-<random>",
  "properties": {
    "hsmUri": "https://mymhsm-<random>.managedhsm.azure.net/",
    "provisioningState": "Succeeded",
    "securityDomainProperties": {
      "activationStatus": "NotActivated",
      "activationStatusMessage": "Your HSM has been provisioned, but cannot be used for cryptographic operations until it is activated. To activate the HSM, download the security domain."
    },
    "softDeleteRetentionInDays": 7,
    "statusMessage": "The Managed HSM is provisioned and ready to use."
  },
  "type": "Microsoft.KeyVault/managedHSMs"
}
```

### 2) Activate the HSM (download Security Domain)

Until activation, data‑plane operations are disabled. Prepare at least **three RSA public keys** and choose a **quorum** (minimum number of private keys required to decrypt the security domain).

To activate the HSM, you send at least 3 (maximum 10) RSA public keys to the HSM. The HSM encrypts the security domain with these keys and sends it back. Once this security domain download is successfully completed, your HSM is ready to use. You also need to specify quorum, which is the minimum number of private keys required to decrypt the security domain.


> [!NOTE]
> Taking the example of a quorum of 2, you can lose one private key and still be able to recover the security domain. If you lose 2 keys, you will not be able to recover the security domain and will need to create a new HSM.

For this case, let's generate 3 self‑signed RSA keys using OpenSSL:

```powershell
# Generate three self‑signed RSA certs (public keys)
openssl req -newkey rsa:2048 -nodes -keyout cert_0.key -x509 -days 365 -out cert_0.cer
openssl req -newkey rsa:2048 -nodes -keyout cert_1.key -x509 -days 365 -out cert_1.cer
openssl req -newkey rsa:2048 -nodes -keyout cert_2.key -x509 -days 365 -out cert_2.cer
```

Then, download the security domain and activate the HSM:

```powershell
az keyvault security-domain download `
  --hsm-name $HSM_NAME `
  --sd-wrapping-keys ./cert_0.cer ./cert_1.cer ./cert_2.cer `
  --sd-quorum 2 `
  --security-domain-file "$HSM_NAME-SD.json"
```

Store the **security domain file** and the RSA **key pairs** securely. You need them for disaster recovery or for creating another HSM that shares the same security domain.

> [!NOTE]
> If you see an error like:
> ```
> No status found in body 
> Content: {"value":"{\"EncData\":{\"data\":...`
>```
> it means the CLI returned the security-domain payload but tripped over its own polling/parse logic. As long as you see the `EncData` JSON, you can ignore this error and proceed. The security domain file should have been created correctly.

You can check that the HSM is fully activated by querying its properties:

```powershell
az keyvault show --hsm-name $HSM_NAME --query "properties.securityDomainProperties"
```
**Expected Output:**

```json
{
  "activationStatus": "Active", 
  "activationStatusMessage": "Your HSM has been activated and can be used for cryptographic operations." 
}
```
Here the `activationStatus` should be `Active` and the `activationStatusMessage` should confirm that the HSM is activated.

### 3) Capture identifiers for reuse

```powershell
$HSM_RESOURCE_ID = az keyvault show --hsm-name $HSM_NAME --query id -o tsv
$HSM_URI = az keyvault show --hsm-name $HSM_NAME --query properties.hsmUri -o tsv
```

### 4) Assign local RBAC for key management
Now that the HSM is activated, you can assign yourself and others local RBAC roles to manage keys in the HSM data plane. For instance, grant yourself key‑management rights in the HSM data plane (local RBAC):

```powershell
az keyvault role assignment create `
  --hsm-name $HSM_NAME `
  --role "Managed HSM Crypto Officer" `
  --assignee-object-id $CURRENT_USER_ID `
  --scope /
```

And the ability to create and manage keys:

```powershell
az keyvault role assignment create `
  --hsm-name $HSM_NAME `
  --role "Managed HSM Crypto User" `
  --assignee-object-id $CURRENT_USER_ID `
  --scope /keys
```

> Common local RBAC roles include **Managed HSM Crypto Officer**, **Managed HSM Crypto User**, and **Managed HSM Crypto Auditor**. For more details, see [About Managed HSM local RBAC built-in roles](https://learn.microsoft.com/en-us/azure/key-vault/managed-hsm/built-in-roles).

### 5) Author the key release policy
Once you have the permissions to create and manage keys in the HSM, you need to create a JSON file that defines the release policy for keys you will create in this HSM. This policy specifies the attestation authority and claims that must be satisfied for a key to be released.
For example, you can create a file named `release-policy.json` with the following content:

```json
{
  "version": "1.0.0",
  "anyOf": [
    {
      "authority": "https://sharedweu.weu.attest.azure.net",
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
> [!TIP]
> The `authority` field specifies the attestation service endpoint. You can use the shared endpoint or create a dedicated attestation provider (see [Provision a Dedicated Microsoft Azure Attestation Provider](../attestation/custom-attestation-provider.md)).

> [!NOTE]
> The `claim` fields specify the conditions that must be met for a key to be released. In this example, the key will only be released to VMs that are genuine Azure Confidential VMs and are configured securely (Azure compliant). Check the [Microsoft Azure Attestation overview](https://learn.microsoft.com/en-us/azure/attestation/overview) for a deeper understanding.

### 6) Create an exportable key with the release policy
Now, create a key in the Managed HSM that is exportable and has the release policy you just defined.

```powershell
$KEY_NAME = "KeyEncryptionKey"

az keyvault key create `
  --hsm-name $HSM_NAME `
  --name $KEK_NAME `
  --kty "RSA-HSM" `
  --exportable `
  --policy "@release-policy.json"
```
This key can now be used for encrypting data (for example, data files or even model weights) and can be released to a Confidential VM that meets the attestation claims defined in the release policy. 

Verify policy was applied:

```powershell
az keyvault key show `
  --hsm-name $HSM_NAME `
  --name $KEY_NAME `
  --query "releasePolicy" -o json
```

Capture the key identifier for later use:
```powershell
$keyJson = az keyvault key show --hsm-name $HSM_NAME --name $KEK_NAME -o json | ConvertFrom-Json
$KEK_KID = $keyJson.key.kid
$KEK_RESOURCE = "$HSM_RESOURCE_ID/keys/$KEK_NAME"
```

Now you have a Managed HSM with an exportable key protected by a release policy. You can use this key for encrypting data and securely releasing it to compliant Confidential VMs.

### 7) (Optionnal) OS-disk encryption with CMK for DES
If you plan to use this key for OS-disk encryption with Customer-Managed Keys (CMK) in a Disk Encryption Set (DES), you can follow the steps in the [OS Disk Encryption with CMK](../os-disk-encryption/os-disk-encryption-cmk.md) module, using the `$KEK_KID` and `$KEK_RESOURCE` variables for the key URL and scope.

## Exports (available after this module)

HSM details for reuse in tutorials:
```powershell
$HSM_NAME
$HSM_RESOURCE_ID
$HSM_URI
```

Key details for reuse in tutorials:
```powershell
$KEY_NAME
$KEK_KID
$KEK_RESOURCE
```

## Continue your tutorial

After completing this module, jump back to the Confidential VM deployment in your tutorial of choice:

| Tutorial                                                 | Continue at                                                  |
| -------------------------------------------------------- | ------------------------------------------------------------ |
| **Confidential ML Training (CPU)**                       | [4. Deploy the Confidential VM](../../tutorials/confidential-ml-training/README.md#4-deploy-the-confidential-vm)                         |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [5. Deploy the Confidential GPU VM](../../tutorials/confidential-llm-inferencing/README.md#5-deploy-the-confidential-gpu-vm)                         |

