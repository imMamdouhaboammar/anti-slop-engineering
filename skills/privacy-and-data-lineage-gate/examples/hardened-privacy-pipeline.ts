// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

/**
 * Hardened Privacy & Data Lineage Pipeline Reference Implementation.
 * Demonstrates:
 * 1. Tainted PII Types (Redacted<T>) preventing log and telemetry leakage
 * 2. Key-per-Subject Cryptographic Erasure (Crypto-Shredding) for immutable ledgers
 * 3. Purpose-Bound Data Minimization with Automated Retention TTL
 * 4. Fenced Telemetry Egress with Differential Privacy
 */

import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { inspect } from "node:util";

// ---------------------------------------------------------------------------
// 1. Tainted PII Types & Compiler-Enforced Boundary Sealing
// ---------------------------------------------------------------------------

declare const BrandSymbol: unique symbol;

export type Branded<T, Brand extends string> = T & { readonly [BrandSymbol]: Brand };

export type RawEmail = Branded<string, "RawEmail">;
export type RawPhone = Branded<string, "RawPhone">;
export type RawIp = Branded<string, "RawIp">;

export interface AuditContext {
  readonly actorId: string;
  readonly reason: "billing_processing" | "security_investigation" | "legal_compliance";
  readonly correlationId: string;
}

export class Redacted<T> {
  private readonly value: T;
  public readonly brandName: string;

  constructor(value: T, brandName = "PII") {
    this.value = Object.freeze(value);
    this.brandName = brandName;
  }

  public toString(): string {
    return `[REDACTED:${this.brandName}]`;
  }

  public toJSON(): string {
    return `[REDACTED:${this.brandName}]`;
  }

  public [inspect.custom](): string {
    return `[Redacted<${this.brandName}>]`;
  }

  /**
   * Explicit cryptographic unwrap requiring audited business purpose.
   */
  public reveal(context: AuditContext): T {
    if (!context || !context.actorId || !context.reason) {
      throw new Error("PRIVACY_VIOLATION: Cannot unwrap Redacted PII without audited context");
    }
    return this.value;
  }
}

export function redactEmail(raw: string): Redacted<RawEmail> {
  const normalized = raw.trim().toLowerCase() as RawEmail;
  return new Redacted<RawEmail>(normalized, "Email");
}

export function redactPhone(raw: string): Redacted<RawPhone> {
  const normalized = raw.replace(/\s+/g, "") as RawPhone;
  return new Redacted<RawPhone>(normalized, "Phone");
}

// ---------------------------------------------------------------------------
// 2. Cryptographic Erasure (Crypto-Shredding) for Immutable Event Ledgers
// ---------------------------------------------------------------------------

export interface EncryptedPayload {
  readonly subjectId: string;
  readonly ivHex: string;
  readonly authTagHex: string;
  readonly ciphertextHex: string;
  readonly recordedAtMs: number;
}

export class SubjectKeyKms {
  private readonly activeKeys = new Map<string, Buffer>();

  public getOrCreateSubjectKey(subjectId: string): Buffer {
    let key = this.activeKeys.get(subjectId);
    if (!key) {
      key = randomBytes(32); // AES-256
      this.activeKeys.set(subjectId, key);
    }
    return key;
  }

  /**
   * Instantaneous Cryptographic Erasure (GDPR Right-to-be-Forgotten).
   * Shredding the user key renders all immutable Kafka/WAL events unreadable.
   */
  public shredSubjectKey(subjectId: string): boolean {
    const key = this.activeKeys.get(subjectId);
    if (!key) return false;
    // Overwrite memory before deleting from map
    key.fill(0);
    this.activeKeys.delete(subjectId);
    return true;
  }

  public hasKey(subjectId: string): boolean {
    return this.activeKeys.has(subjectId);
  }
}

export function encryptForImmutableLedger(
  subjectId: string,
  plaintextJson: string,
  kms: SubjectKeyKms
): EncryptedPayload {
  const key = kms.getOrCreateSubjectKey(subjectId);
  const iv = randomBytes(12); // Standard 96-bit IV for AES-GCM
  const cipher = createCipheriv("aes-256-gcm", key, iv);

  const ciphertext = Buffer.concat([cipher.update(plaintextJson, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();

  return {
    subjectId,
    ivHex: iv.toString("hex"),
    authTagHex: authTag.toString("hex"),
    ciphertextHex: ciphertext.toString("hex"),
    recordedAtMs: Date.now(),
  };
}

export function decryptFromImmutableLedger(
  payload: EncryptedPayload,
  kms: SubjectKeyKms
): string {
  if (!kms.hasKey(payload.subjectId)) {
    throw new Error(`CRYPTO_SHREDDED: Subject ${payload.subjectId} key has been shredded; data is cryptographically unrecoverable.`);
  }

  const key = kms.getOrCreateSubjectKey(payload.subjectId);
  const iv = Buffer.from(payload.ivHex, "hex");
  const authTag = Buffer.from(payload.authTagHex, "hex");
  const ciphertext = Buffer.from(payload.ciphertextHex, "hex");

  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAuthTag(authTag);

  const decrypted = Buffer.concat([decipher.update(ciphertext), decipher.final()]);
  return decrypted.toString("utf8");
}

// ---------------------------------------------------------------------------
// 3. Purpose-Bound Data Minimization & Retention TTL
// ---------------------------------------------------------------------------

export type PurposeBinding = "AUTHENTICATION" | "BILLING" | "LEGAL_AUDIT" | "ANALYTICS_OPT_IN";

export interface DataFieldPolicy {
  readonly name: string;
  readonly purpose: PurposeBinding;
  readonly retentionTtlDays: number;
  readonly isPii: boolean;
}

export interface SchemaRetentionContract {
  readonly tableName: string;
  readonly purpose: PurposeBinding;
  readonly retentionTtlDays: number;
  readonly fields: readonly DataFieldPolicy[];
}

export function validateSchemaPrivacyContract(contract: SchemaRetentionContract): void {
  if (!contract.purpose) {
    throw new Error(`PRIVACY_CONTRACT_VIOLATION: Table ${contract.tableName} lacks declared purpose binding.`);
  }
  if (!contract.retentionTtlDays || contract.retentionTtlDays <= 0) {
    throw new Error(`PRIVACY_CONTRACT_VIOLATION: Table ${contract.tableName} must declare a non-zero retentionTtlDays.`);
  }
  for (const field of contract.fields) {
    if (field.isPii && (!field.purpose || field.retentionTtlDays <= 0)) {
      throw new Error(`PRIVACY_CONTRACT_VIOLATION: PII field ${field.name} in table ${contract.tableName} lacks valid retention policy.`);
    }
  }
}

// ---------------------------------------------------------------------------
// 4. Fenced Telemetry Egress with Differential Privacy
// ---------------------------------------------------------------------------

export interface TelemetryEvent {
  readonly eventName: string;
  readonly timestamp: number;
  readonly attributes: Record<string, string | number | boolean>;
}

export function sanitizeAndEmitTelemetry(
  rawEvent: {
    name: string;
    email?: Redacted<RawEmail> | string;
    phone?: Redacted<RawPhone> | string;
    latencyMs: number;
  },
  allowedSinks: readonly string[]
): TelemetryEvent {
  if (!allowedSinks.includes("internal_metrics")) {
    throw new Error("PRIVACY_FENCE_VIOLATION: Unauthorized telemetry sink target");
  }

  // Laplace noise injection for differential privacy on numeric metrics (epsilon = 1.0)
  const u = Math.random() - 0.5;
  const b = 1.0 / 1.0;
  const laplaceNoise = -b * Math.sign(u) * Math.log(1 - 2 * Math.abs(u));
  const dpMetric = Math.max(0, Math.round(rawEvent.latencyMs + laplaceNoise));

  // Raw PII is completely stripped. Only privacy-preserving coarse metrics are emitted.
  return {
    eventName: rawEvent.name,
    timestamp: Date.now(),
    attributes: {
      latencyMsEstimateDp: dpMetric,
      hasEmailRecorded: Boolean(rawEvent.email),
    },
  };
}
