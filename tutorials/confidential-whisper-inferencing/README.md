# Confidential Whisper + LLM Pipeline – End-to-End Secure Audio Intelligence

> **Focus**: This tutorial extends our [Confidential GPU VM setup](../confidential-llm-inferencing/README.md) by adding [Azure's Confidential Whisper service](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-confidential-inferencing-preview/4248181) for secure audio transcription. We'll demonstrate how to build a complete confidential AI pipeline that processes sensitive audio data through transcription to LLM reasoning, all while maintaining end-to-end encryption. The key innovation here is the use of Oblivious HTTP (OHTTP) with Hardware-Protected Key Exchange (HPKE) to ensure that even Azure's infrastructure cannot see your audio data in plaintext – only the TEE-protected Whisper model can decrypt and process it.

## Introduction: Why Confidential Audio Processing Matters

In the tutorial [Confidential LLM Inference](../confidential-llm-inferencing/README.md), we've secured text-based LLM inference using Confidential VMs. But what about audio data? Consider these scenarios:

- **Healthcare**: Patient consultations recorded for diagnosis assistance
- **Legal**: Confidential depositions that need transcription and analysis
- **Financial**: Earnings calls with market-sensitive information
- **Personal Assistants**: Voice commands containing private user data

Traditional audio transcription services require you to trust the service provider with your raw audio. Even with TLS encryption in transit, the audio is decrypted at the service boundary and processed in plaintext. This creates significant privacy and compliance challenges.

**Confidential Whisper changes this paradigm entirely**. Using the same hardware-based confidential computing principles we've explored, combined with a novel application of OHTTP, we can ensure that:

1. **Audio remains encrypted** until it reaches the TEE-protected Whisper model
2. **No intermediary** (not even Azure's load balancers) can access the plaintext audio
3. **Cryptographic attestation** proves the audio is only processed in a verified, secure environment
4. **End-to-end pipeline security** from audio input through transcription to LLM analysis

For a complete deep dive on these concepts, see [Azure AI Confidential Inferencing: Technical Deep-Dive](https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/azure-ai-confidential-inferencing-technical-deep-dive/4253150).

## Key Concepts: OHTTP and HPKE Explained

Before we dive into implementation, let's understand the cryptographic innovations that make this possible.

### What is OHTTP (Oblivious HTTP)?

[Oblivious HTTP (RFC 9458)](https://datatracker.ietf.org/doc/rfc9458/) is a protocol that adds an additional layer of encryption to HTTP requests, designed to prevent intermediaries from linking requests to users or seeing request contents.

**Traditional HTTPS**:
```
Client --[TLS encrypted]→ Load Balancer --[decrypt/re-encrypt]→ Server
```
*Problem*: The load balancer sees plaintext.

**OHTTP**:
```
Client --[HPKE encrypted payload inside TLS]→ Load Balancer --[still encrypted]→ TEE Server
```
*Solution*: Only the final TEE server can decrypt.

### What is HPKE (Hybrid Public Key Encryption)?

[HPKE (RFC 9180)](https://datatracker.ietf.org/doc/rfc9180/) is a modern encryption scheme that combines:
- **Asymmetric cryptography** for key exchange (like RSA/ECDH)
- **Symmetric cryptography** for actual data encryption (like AES-GCM)
- **Key encapsulation** for forward secrecy

Think of it as a more efficient, modern replacement for the "encrypt data with AES, then encrypt the AES key with RSA" pattern, but with better security properties.

### The KMS (Key Management Service) Role

Azure's Confidential Inferencing KMS is a special service that:
1. **Manages HPKE public keys** for all Confidential Whisper instances
2. **Rotates keys regularly** for forward secrecy
3. **Only releases private keys** to attested TEE environments
4. **Provides public keys** to any client for encryption

This creates a powerful security property: clients can encrypt data that only verified TEE environments can decrypt.

## Prerequisites and Environment Setup

### What You'll Need

Building on our previous tutorial, you should already have:
- ✅ A Confidential GPU VM running your LLM (from Tutorial 2)
- ✅ The VM exposed via HTTPS with Caddy and API authentication
- ✅ A working Streamlit client for LLM interaction

Additionally, you'll need:
- 📝 Access to [Azure AI Foundry's Confidential Whisper preview](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-confidential-inferencing-preview/4248181)
- 💻 A client environment (your laptop or a small Azure VM)
- 🔧 Build tools for compiling the OHTTP client

## Step 0: Requesting Confidential Whisper Access

> [!IMPORTANT]
> As of this writing, Confidential Whisper is in preview.

Navigate to [confidential inferencing with the Azure OpenAI Service Whisper model preview](https://forms.office.com/Pages/ResponsePage.aspx?id=v4j5cvGGr0GRqy180BHbR8P2BSe126RNkgWDe_NYrL1UMlk5R0szS1ZMVEVRN0s5TEMzU0JVVThETy4u). Once approved, you'll be able to set up your endpoint and API key for confidential whisper on Azure AI Foundry.

## Step 1: Setting Up the Client Environment

We'll create a dedicated environment for our OHTTP-enabled client. You have two options:

### Option A: Use Your Local Machine

If you prefer to run everything locally, you can use your existing development machine. This works on:
- Windows (via WSL2)
- macOS
- Linux

The client will run on `http://localhost:8501` and won't require any firewall changes.

### Option B: Create a Dedicated Client VM

For a more isolated, shareable demo environment, let's create a small Azure VM:

```powershell
# PowerShell - Define our client infrastructure
$CLIENT_RESOURCE_GROUP = "confidential-whisper-client-rg"
$LOCATION = "eastus2"  # Same region as your Confidential GPU VM
$CLIENT_VM_NAME = "whisper-client-vm"
$CLIENT_VNET_NAME = "whisper-client-vnet"
$CLIENT_SUBNET_NAME = "default"
$ADMIN_USERNAME = "azureuser"
$SSH_KEY_PATH = "$HOME\.ssh\id_rsa.pub"

# Create the resource group
az group create `
  --name $CLIENT_RESOURCE_GROUP `
  --location $LOCATION

# Create a virtual network for the client
az network vnet create `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --name $CLIENT_VNET_NAME `
  --address-prefix "10.3.0.0/16" `
  --subnet-name $CLIENT_SUBNET_NAME `
  --subnet-prefix "10.3.0.0/24"

# Create the client VM (small size is sufficient)
az vm create `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --name $CLIENT_VM_NAME `
  --image "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest" `
  --size "Standard_B2s" `
  --admin-username $ADMIN_USERNAME `
  --ssh-key-values $SSH_KEY_PATH `
  --vnet-name $CLIENT_VNET_NAME `
  --subnet $CLIENT_SUBNET_NAME `
  --public-ip-sku Standard

# Get the public IP for SSH access
$CLIENT_PUBLIC_IP = az vm show -d `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --name $CLIENT_VM_NAME `
  --query "publicIps" -o tsv

Write-Host "Client VM created. SSH access: ssh $ADMIN_USERNAME@$CLIENT_PUBLIC_IP" -ForegroundColor Green
```

Now, let's configure network security to allow Streamlit access (port 8501) only from your IP:

```powershell
# Get your current public IP
$MY_PUBLIC_IP = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing).Content
Write-Host "Your public IP: $MY_PUBLIC_IP" -ForegroundColor Cyan

# Get the NSG associated with the client VM
$nicId = az vm show `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --name $CLIENT_VM_NAME `
  --query "networkProfile.networkInterfaces[0].id" -o tsv
  
$nicName = ($nicId -split "/")[-1]

$nsgId = az network nic show `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --name $nicName `
  --query "networkSecurityGroup.id" -o tsv
  
$nsgName = ($nsgId -split "/")[-1]

# Add rule to allow Streamlit access from your IP only
az network nsg rule create `
  --resource-group $CLIENT_RESOURCE_GROUP `
  --nsg-name $nsgName `
  --name "AllowStreamlitFromMyIP" `
  --priority 200 `
  --direction Inbound `
  --access Allow `
  --protocol Tcp `
  --source-address-prefixes "$MY_PUBLIC_IP/32" `
  --destination-port-ranges 8501 `
  --description "Allow Streamlit access from developer IP only"

Write-Host "NSG rule added. Streamlit will be accessible at: http://${CLIENT_PUBLIC_IP}:8501" -ForegroundColor Green
```

### Connecting to Your Client Environment

SSH into your client VM (or open a terminal if working locally):

```bash
ssh azureuser@<CLIENT_PUBLIC_IP>
```

## Step 2: Installing Build Dependencies and OHTTP Client

The Microsoft OHTTP client is written in Rust and provides Python bindings. We need to set up a complete build environment.

### Understanding the Build Requirements

The OHTTP client requires:
- **Rust toolchain**: For compiling the core OHTTP implementation
- **OpenSSL development libraries**: For cryptographic operations
- **Python development headers**: For building Python bindings
- **Build tools**: gcc, make, cmake for compilation

```bash
# Update package manager
sudo apt-get update

# Install system dependencies
sudo apt-get install -y \
    curl \
    build-essential \
    git \
    jq \
    cmake \
    python3-venv \
    python3-dev \
    libssl-dev \
    pkg-config \
    ca-certificates

# Install Rust (required for building the OHTTP client)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Load Rust environment
source $HOME/.cargo/env

# Verify installations
rustc --version
python3 --version
cmake --version
```

> [!NOTE]
> **Why Rust?** The OHTTP client is implemented in Rust for memory safety and performance. Rust's ownership system prevents many security vulnerabilities that could compromise the encryption.

## Step 3: Building Microsoft's Attested OHTTP Client

Now we'll build the Python bindings for the OHTTP client:

```bash
# Clone Microsoft's attested OHTTP client repository
cd ~
git clone https://github.com/microsoft/attested-ohttp-client.git
cd attested-ohttp-client

# The repository includes a build script for Python bindings
./scripts/build-pyohttp.sh
```

> **What's happening during the build?**
> 1. Rust code is compiled to a native library
> 2. Python bindings are generated using PyO3/Maturin
> 3. A Python wheel package is created in `target/wheels/`

Let's install the built package:

```bash
# Create a Python virtual environment for our client
cd ~
python3 -m venv whisper-client-env
source whisper-client-env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install the OHTTP client wheel
pip install ~/attested-ohttp-client/target/wheels/*.whl

# Verify installation
python -c "import pyohttp; print('OHTTP client successfully installed')"
```

## Step 4: Validating OHTTP Connectivity

Before building our full application, let's verify that OHTTP is working correctly with Azure's Confidential Inferencing infrastructure.

### Understanding the Validation Flow

This test will:
1. Connect to Azure's KMS to fetch HPKE public keys
2. Encrypt a test request using OHTTP
3. Send it to a Confidential Whisper endpoint
4. Verify we get a valid response

### Docker-Based Quick Test (Recommended)

Microsoft provides a pre-built Docker image for testing. This is the fastest way to validate your setup:

```bash
# Set your Confidential Whisper credentials
export WHISPER_ENDPOINT="https://<your-endpoint>.eastus2.inference.ml.azure.com/whisper/transcriptions"
export WHISPER_API_KEY="<your-whisper-api-key>"
export KMS_URL="https://accconfinferenceproduction.confidential-ledger.azure.com"

# Download a sample audio file for testing
wget https://github.com/Azure-Samples/cognitive-services-speech-sdk/raw/master/samples/csharp/sharedcontent/console/whatstheweatherlike.wav \
  -O test_audio.wav

# Run the Docker test
docker run \
  -e KMS_URL=${KMS_URL} \
  -v $(pwd)/test_audio.wav:/test_audio.wav \
  mcr.microsoft.com/acc/samples/attested-ohttp-client:latest \
  ${WHISPER_ENDPOINT} \
  -F "file=@/test_audio.wav" \
  -O "api-key: ${WHISPER_API_KEY}" \
  -F "response_format=json"
```

**Expected output:**
```json
{
  "text": "The quick brown fox jumped over a dog."
}
```

If you see this transcription, OHTTP is working correctly!

### Understanding What Just Happened

Let's break down what occurred in this test:

1. **KMS Discovery**: The client contacted the KMS at the specified URL
2. **Certificate Fetch**: Retrieved the KMS's TLS certificate for secure communication
3. **Key Exchange**: Obtained the current HPKE public keys for Confidential Whisper
4. **OHTTP Encryption**: 
   - Generated an ephemeral key pair
   - Encrypted the audio file with HPKE
   - Wrapped everything in OHTTP format
5. **Transmission**: Sent the double-encrypted request through Azure's infrastructure
6. **TEE Processing**: Only the Confidential Whisper instance (in its TEE) could decrypt
7. **Response**: Received the transcription, also encrypted via OHTTP

The beauty of this system: Azure's load balancers, gateways, and monitoring systems saw **only encrypted blobs**. The audio was never exposed outside the TEE.

## Step 5: Building the Integrated Client Application

Now let's create a sophisticated Streamlit application that combines Confidential Whisper with your existing Confidential LLM.

### Application Architecture

Our client will provide:
- 🎙️ Audio file upload interface
- 🔐 OHTTP encryption for Whisper calls
- 📝 Transcript display
- 🤖 Automatic LLM analysis of transcripts
- 💬 Full conversation history

### Installing Client Dependencies

```bash
# Activate our virtual environment
source ~/whisper-client-env/bin/activate

# Install required packages
pip install \
    streamlit==1.32.0 \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    aiofiles==24.1.0
```

### Creating Configuration File

First, let's set up our configuration with proper secret management:

```bash
# Create a .env file for configuration
nano ~/whisper_client.env
```

Then add the following content:
```bash
# === Confidential Whisper Configuration ===
KMS_URL=https://accconfinferenceproduction.confidential-ledger.azure.com
WHISPER_ENDPOINT=<your-whisper-endpoint-url>
WHISPER_API_KEY=<your-whisper-api-key>

# === Your Confidential LLM Configuration ===
LLM_ENDPOINT=https://<your-llm-fqdn>/v1/chat/completions
LLM_API_KEY=<your-llm-api-key>
LLM_MODEL=/dev/shm/decrypted_model
```

Now, we can use this configuration in a Streamlit application (a sample one is provided to you in [streamlit_client.py](./src/streamlit_client.py)) to securely interact with both the Confidential Whisper and LLM services. The streamlit application will be an enhanced version of the one described in the previous tutorial that adds this whisper part.

You can now run it with
```bash
source .venv/bin/activate
streamlit run streamlit_client.py --server.port 8501 --server.address 0.0.0.0
```
You can access to your Streamlit app at `http://<your-vm-ip>:8501`.
This application allows you to upload an audio file, which is securely transcribed using Confidential Whisper via OHTTP. The resulting transcript is displayed and can be automatically sent to your Confidential LLM for further analysis or response generation.