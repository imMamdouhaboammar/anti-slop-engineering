# Apple Privacy Engineering Playbook

> Implementing on-device intelligence, differential privacy budgets, and zero-knowledge client architectures.

## Core Operational Principles

Apple's privacy architecture is built on the tenet that **user privacy cannot be compromised for functional convenience**. The architecture guarantees security even if the backend infrastructure is fully breached.

---

## 1. On-Device Processing First

All computations that can occur locally on the user's device must execute on-device:
- Search indexing, facial recognition, photo categorizing, speech-to-text, and predictive text modeling execute locally.
- Only non-identifiable, aggregated model gradients or differential-privacy perturbed summary statistics are transmitted upstream.
- If server processing is required, process in ephemeral memory and discard without writing to disk.

---

## 2. Local Differential Privacy ($\epsilon$-Budget Enforcement)

When telemetry or feature analytics must be gathered from client devices, apply **Local Differential Privacy (LDP)** before data leaves the client device.

### Parameterization Rules

$$\epsilon \le 1.0 \quad (\text{Strict Privacy Budget})$$

1. **Noise Injection (Laplace Mechanism):**
   For any numeric metric $x$ with global sensitivity $\Delta f$:
   $$\text{perturbed\_value} = x + \text{Laplace}\left(0, \frac{\Delta f}{\epsilon}\right)$$
2. **Count-Min Sketch with Randomized Response:**
   For string tokens or discrete categorical events, apply randomized response bit-flipping: each bit is retained with probability $p = \frac{e^{\epsilon / 2}}{e^{\epsilon / 2} + 1}$ and flipped with probability $1 - p$.
3. **No Per-User Telemetry Timestamps:**
   Strip milliseconds and exact timestamps; batch client telemetry into coarse 24-hour transmission windows with randomized jitter delays.

---

## 3. Apple Private Click Measurement & Coarse Attribution

When tracking campaign conversions or click-through attribution:
1. **Zero Third-Party Cookies / Web Storage:** Do not use cross-site storage.
2. **Entropy Limits:**
   - Source Event ID capped at 8 bits (values $0 \dots 255$).
   - Conversion Value capped at 4 bits (values $0 \dots 15$).
3. **Randomized Delivery Delays:**
   Attribution reports must be queued and delayed by 24 to 48 hours to prevent timing correlation attacks.

---

## 4. Hardware Security Enclave Boundaries

On native Apple platforms (iOS/macOS) and cloud equivalents (AWS Nitro Enclaves, GCP Confidential VMs):
1. User private keys must reside in the hardware Secure Enclave.
2. The operating system kernel and server hypervisor cannot extract the private key; all signing and decryption operations occur inside the hardware boundary.
3. Key destruction is instant and physically permanent.
