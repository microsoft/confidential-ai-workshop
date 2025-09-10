# Provision a Dedicated Microsoft Azure Attestation Provider

## Overview

While Azure provides shared attestation provider, for some use cases it can be interesting to have a dedicated endpoint.

Your own attestation provider gives you a dedicated endpoint for attestation validation and enables additional customization options.

## Prerequisites

* Active Azure subscription with permissions to create Microsoft.Attestation resources.
* Azure CLI installed and logged in (`az login`).
* Existing resource group and region variables, for example:

  ```powershell
  $RESOURCE_GROUP="MyConfidentialRG"
  $LOCATION="westeurope"
  ```

## Procedure

```powershell
$ATTESTATION_PROVIDER="attestprovider$(Get-Random)"
```

```powershell
# Create the attestation provider
az attestation create --name $ATTESTATION_PROVIDER --resource-group $RESOURCE_GROUP --location $LOCATION
```

**Expected Output:**

```json
{
  "attestUri": "https://attestprovider<random>.<location>.attest.azure.net",
  "id": "/subscriptions/your-subscription-id/resourceGroups/MyConfidentialRG/providers/Microsoft.Attestation/attestationProviders/attestprovider<random>",
  "location": "<location>",
  "name": "attestprovider<random>",
  "resourceGroup": "MyConfidentialRG",
  "status": "Ready",
  "trustModel": "AAD",
  "type": "Microsoft.Attestation/attestationProviders"
}
```

Now store the value of your attestation URI to be able to use it for further use.

```powershell
$ATTEST_URI = az attestation show --name $ATTESTATION_PROVIDER --resource-group $RESOURCE_GROUP --query "attestUri" -o tsv
```

This approach gives you fine-grained control but requires more maintenance and understanding of attestation concepts. For more details see [About Microsoft Azure Attestation](https://learn.microsoft.com/en-us/azure/attestation/overview).

## Continue your tutorial

| Tutorial                               | Continue at                                                                                                                                                                                                      |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Confidential ML Training (CPU)**     | [3.5. Create an Exportable Key with Release Policy](../../tutorials/confidential-ml-training/README.md#35-create-an-exportable-key-with-release-policy) |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [4.3. Definition of the release policy](../../tutorials/confidential-llm-inferencing/README.md#43-definition-of-the-release-policy)                                                                        |
