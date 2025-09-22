# Attestation Modules (Microsoft Azure Attestation)

## Overview

Use these modules when your tutorial needs to **set or customize the attestation authority** used in Secure Key Release (SKR). Most quick starts work with Azure’s **shared** attestation endpoints, but some organizations prefer a **dedicated Microsoft Azure Attestation (MAA)** provider for isolation, governance, or regional routing.

## Choose your path

| Option                             | When to choose                                                             | What you get                                           | Setup effort                                        |
| ---------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------- |
| **Shared Attestation (default)**   | Fast start, PoCs, demos                                                    | Microsoft‑operated shared MAA endpoint (regional)      | **None** – already available                        |
| **Dedicated Attestation Provider** | Enterprise controls, isolation, consistent endpoint name, audit separation | Your own MAA resource with a **tenant‑owned** endpoint | **Low** – provision once and reuse across tutorials |

> \[!NOTE]
> SKR policies reference an **attestation authority URL** (e.g., `https://sharedweu.weu.attest.azure.net` or `https://<your-name>.<region>.attest.azure.net`). Both shared and dedicated endpoints validate AMD SEV‑SNP CVM claims used by the tutorials.

---

## Prerequisites

* Azure CLI logged in (`az login`).
* A resource group and region:

  ```powershell
  $RESOURCE_GROUP = "MyConfidentialRG"
  $LOCATION = "westeurope"
  ```
* Permissions to create **Microsoft.Attestation/attestationProviders** (for the dedicated option).

> \[!IMPORTANT]
> Keep the **region** of your attestation provider aligned with your Key Vault / Managed HSM release policies and your CVM region strategy.

---

## Modules in this folder

### 1) Provision a Dedicated Attestation Provider

**File:** [`custom-attestation-provider.md`](./custom-attestation-provider.md)

What it does:

* Creates your **own** attestation provider (MAA) with a dedicated endpoint.
* Exports the authority URL into a shell variable you can reuse in policies.

**Exports you’ll reuse:**

```powershell
$ATTESTATION_PROVIDER   # The MAA resource name you created
$ATTEST_URL             # The full authority URL (https://<name>.<region>.attest.azure.net)
```

**Where it plugs into the tutorials:**

* Any step where you author a **release policy** and need to set `"authority": "<attestation-url>"`.
* Replace the shared URL with your `$ATTEST_URL` and continue.

> \[!TIP]
> After running the module, set a convenience variable in your shell so the main tutorial snippets keep working:
>
> ```powershell
> $ATTEST_URL = "$ATTEST_URL"   # ensure it’s loaded in the current session
> ```

---

## How to reference this module from tutorials

Use a **GitHub callout** right before (or inside) the section that defines the release policy:

```markdown
> [!TIP]
> **Need a dedicated attestation endpoint?**
> Run the module: [Provision a Dedicated MAA Provider](../../modules/attestation/custom-attestation-provider.md),
> then set `$ATTEST_URL` to your new authority (e.g., `https://<name>.<region>.attest.azure.net`) and return here.
```

You can keep the tutorial defaulting to a **shared** authority and let advanced users click through to the module when needed.

---

## Continue your tutorial

After finishing the (optional) dedicated attestation provider module, jump back to the section where the **release policy** is authored:

| Tutorial                                                 | Continue at                                                                                                                         |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Confidential ML Training (CPU)**                       | [3.4. Create the release policy file](../../tutorials/confidential-ml-training/README.md#34-create-the-release-policy-file)         |
| **Confidential LLM Inferencing (CPU + GPU Accelerated)** | [4.3. Definition of the release Policy](../../tutorials/confidential-llm-inferencing/README.md#43-definition-of-the-release-policy) |
| **Confidential Whisper Pipeline**                        | (Coming soon) Will reference the attestation authority used by the SKR‑backed keys.                                                 |

> \[!NOTE]
> Anchors may evolve as tutorials are refined. If a link breaks, search for the **release policy** step in the target tutorial.

---

## Outputs (to carry forward)

Keep these variables handy after completing any attestation module:

```powershell
$ATTESTATION_PROVIDER   # Only for the dedicated option
$ATTEST_URL             # Shared or dedicated authority URL used in your policies
```

These values plug directly into the **`authority`** field inside your SKR release policy JSON.
