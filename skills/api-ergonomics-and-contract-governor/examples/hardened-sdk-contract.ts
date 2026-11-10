/**
 * Hardened Reference SDK: API Ergonomics & Contract Governance
 *
 * Demonstrates:
 * 1. Microsoft TypeScript Compiler Rigor (Branded Types, Discriminated Unions, Exhaustive Checking)
 * 2. Stripe World-Class DX (Pit of Success Defaults, Idempotency, Cursor Pagination)
 * 3. 3-Tier Progressive Disclosure (1-liner -> Options bag -> ClientBuilder / Raw request)
 * 4. RFC 9457 Problem Details Standardized Error Model
 */

declare const BrandSymbol: unique symbol;
export type Brand<T, B extends string> = T & { readonly [BrandSymbol]: B };

// --- Branded Nominal Domain Types ---
export type CustomerId = Brand<string, "CustomerId">;
export type PaymentIntentId = Brand<string, "PaymentIntentId">;
export type IdempotencyKey = Brand<string, "IdempotencyKey">;
export type CurrencyCode = Brand<string, "CurrencyCode">;
export type ApiKey = Brand<string, "ApiKey">;

export function asCustomerId(id: string): CustomerId {
  if (!id.startsWith("cus_")) {
    throw new TypeError(`Invalid CustomerId: must start with 'cus_', got '${id}'`);
  }
  return id as CustomerId;
}

export function asPaymentIntentId(id: string): PaymentIntentId {
  if (!id.startsWith("pi_")) {
    throw new TypeError(`Invalid PaymentIntentId: must start with 'pi_', got '${id}'`);
  }
  return id as PaymentIntentId;
}

export function asIdempotencyKey(key: string): IdempotencyKey {
  if (key.trim().length === 0) {
    throw new TypeError("IdempotencyKey cannot be empty");
  }
  return key as IdempotencyKey;
}

export function asCurrencyCode(code: string): CurrencyCode {
  const normalized = code.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(normalized)) {
    throw new TypeError(`Invalid ISO 4217 CurrencyCode: expected 3 letters, got '${code}'`);
  }
  return normalized as CurrencyCode;
}

export function asApiKey(key: string): ApiKey {
  if (!key.startsWith("sk_")) {
    throw new TypeError(`Invalid ApiKey: must start with 'sk_', got '${key}'`);
  }
  return key as ApiKey;
}

// --- RFC 9457 Problem Details Standard ---
export interface InvalidParam {
  readonly name: string;
  readonly reason: string;
  readonly code: string;
}

export interface ProblemDetailsPayload {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail: string;
  readonly instance: string;
  readonly code: string;
  readonly retryable: boolean;
  readonly invalid_params?: readonly InvalidParam[];
  readonly suggested_action?: string;
  readonly doc_url?: string;
}

export class ProblemDetailsError extends Error {
  readonly type: string;
  readonly title: string;
  readonly status: number;
  readonly detail: string;
  readonly instance: string;
  readonly code: string;
  readonly retryable: boolean;
  readonly invalid_params: readonly InvalidParam[];
  readonly suggested_action?: string;
  readonly doc_url?: string;

  constructor(payload: ProblemDetailsPayload) {
    super(`[${payload.code}] ${payload.title}: ${payload.detail}`);
    this.name = "ProblemDetailsError";
    this.type = payload.type;
    this.title = payload.title;
    this.status = payload.status;
    this.detail = payload.detail;
    this.instance = payload.instance;
    this.code = payload.code;
    this.retryable = payload.retryable;
    this.invalid_params = payload.invalid_params ?? [];
    this.suggested_action = payload.suggested_action;
    this.doc_url = payload.doc_url;
  }

  toJSON(): ProblemDetailsPayload {
    return {
      type: this.type,
      title: this.title,
      status: this.status,
      detail: this.detail,
      instance: this.instance,
      code: this.code,
      retryable: this.retryable,
      invalid_params: this.invalid_params,
      suggested_action: this.suggested_action,
      doc_url: this.doc_url,
    };
  }
}

// --- Discriminated Union: Illegal States Unrepresentable ---
export interface RequiresPaymentMethodIntent {
  readonly status: "requires_payment_method";
  readonly id: PaymentIntentId;
  readonly amount: number;
  readonly currency: CurrencyCode;
  readonly clientSecret: string;
}

export interface RequiresConfirmationIntent {
  readonly status: "requires_confirmation";
  readonly id: PaymentIntentId;
  readonly amount: number;
  readonly currency: CurrencyCode;
  readonly paymentMethodId: string;
}

export interface SucceededIntent {
  readonly status: "succeeded";
  readonly id: PaymentIntentId;
  readonly amount: number;
  readonly currency: CurrencyCode;
  readonly chargeId: string;
  readonly completedAt: string;
}

export interface CanceledIntent {
  readonly status: "canceled";
  readonly id: PaymentIntentId;
  readonly amount: number;
  readonly currency: CurrencyCode;
  readonly cancellationReason: "duplicate" | "fraudulent" | "requested_by_customer" | "abandoned";
  readonly canceledAt: string;
}

export type PaymentIntent =
  | RequiresPaymentMethodIntent
  | RequiresConfirmationIntent
  | SucceededIntent
  | CanceledIntent;

export function assertNever(x: never, message?: string): never {
  throw new Error(message ?? `Unexpected unreachable discriminated variant: ${JSON.stringify(x)}`);
}

// --- Pagination Contract ---
export interface CursorPageParams {
  readonly limit?: number;
  readonly startingAfter?: string;
  readonly endingBefore?: string;
}

export interface PaginatedList<T> {
  readonly object: "list";
  readonly data: readonly T[];
  readonly hasMore: boolean;
  readonly nextCursor: string | null;
}

// --- Client Configuration & Pit of Success Defaults ---
export interface ClientOptions {
  readonly apiKey: ApiKey;
  readonly baseUrl?: string;
  readonly defaultTimeoutMs?: number;
  readonly maxRetries?: number;
  readonly fetcher?: typeof fetch;
}

export interface RequestOptions {
  readonly idempotencyKey?: IdempotencyKey;
  readonly timeoutMs?: number;
  readonly signal?: AbortSignal;
  readonly headers?: Record<string, string>;
}

export interface CreatePaymentIntentParams {
  readonly amount: number;
  readonly currency: CurrencyCode;
  readonly customerId?: CustomerId;
  readonly captureMethod?: "automatic" | "manual";
  readonly metadata?: Record<string, string>;
}

// --- SDK Resource Hierarchy (Progressive Disclosure) ---
export class PaymentIntentsResource {
  readonly #client: ResilientHttpClient;

  constructor(client: ResilientHttpClient) {
    this.#client = client;
  }

  // Tier 1 & Tier 2: 1-liner with optional typed options bag
  async create(
    params: CreatePaymentIntentParams,
    options?: RequestOptions
  ): Promise<PaymentIntent> {
    if (params.amount <= 0 || !Number.isInteger(params.amount)) {
      throw new ProblemDetailsError({
        type: "https://api.billing.example.com/errors/invalid_parameters",
        title: "Invalid Amount",
        status: 400,
        detail: `Amount must be a positive integer in minor units (cents), got ${params.amount}`,
        instance: "/v1/payment_intents",
        code: "invalid_amount",
        retryable: false,
        invalid_params: [{ name: "amount", reason: "Must be a positive integer", code: "not_positive_integer" }],
        suggested_action: "Provide amount in smallest currency unit (e.g. 5000 for $50.00).",
      });
    }

    return this.#client.request<PaymentIntent>("POST", "/v1/payment_intents", params, options);
  }

  async retrieve(id: PaymentIntentId, options?: RequestOptions): Promise<PaymentIntent> {
    return this.#client.request<PaymentIntent>("GET", `/v1/payment_intents/${id}`, undefined, options);
  }

  async list(params?: CursorPageParams, options?: RequestOptions): Promise<PaginatedList<PaymentIntent>> {
    const limit = Math.min(Math.max(params?.limit ?? 20, 1), 100);
    const query = new URLSearchParams();
    query.set("limit", limit.toString());
    if (params?.startingAfter) query.set("starting_after", params.startingAfter);
    if (params?.endingBefore) query.set("ending_before", params.endingBefore);

    return this.#client.request<PaginatedList<PaymentIntent>>(
      "GET",
      `/v1/payment_intents?${query.toString()}`,
      undefined,
      options
    );
  }
}

// --- Tier 3: Core Resilient HTTP Client & Power Primitives ---
export class ResilientHttpClient {
  readonly #apiKey: ApiKey;
  readonly #baseUrl: string;
  readonly #defaultTimeoutMs: number;
  readonly #maxRetries: number;
  readonly #fetcher: typeof fetch;

  constructor(options: ClientOptions) {
    this.#apiKey = options.apiKey;
    this.#baseUrl = options.baseUrl ?? "https://api.billing.example.com";
    this.#defaultTimeoutMs = options.defaultTimeoutMs ?? 10_000;
    this.#maxRetries = options.maxRetries ?? 3;
    this.#fetcher = options.fetcher ?? globalThis.fetch;
  }

  async request<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    body?: unknown,
    options?: RequestOptions
  ): Promise<T> {
    const url = `${this.#baseUrl}${path}`;
    const timeoutMs = options?.timeoutMs ?? this.#defaultTimeoutMs;
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    const combinedSignal = options?.signal
      ? AbortSignal.any([options.signal, timeoutSignal])
      : timeoutSignal;

    // Idempotency: Auto-generate UUID if not provided on mutations
    const idempotencyKey =
      options?.idempotencyKey ??
      (method === "POST" ? (`idem_${crypto.randomUUID()}` as IdempotencyKey) : undefined);

    let attempt = 0;
    let delayMs = 100;

    while (attempt <= this.#maxRetries) {
      attempt++;
      try {
        const headers: Record<string, string> = {
          "Authorization": `Bearer ${this.#apiKey}`,
          "Content-Type": "application/json",
          "Accept": "application/json",
          ...options?.headers,
        };
        if (idempotencyKey) {
          headers["Idempotency-Key"] = idempotencyKey;
        }

        const response = await this.#fetcher(url, {
          method,
          headers,
          body: body ? JSON.stringify(body) : undefined,
          signal: combinedSignal,
        });

        if (!response.ok) {
          const isRetryable = [408, 429, 500, 502, 503, 504].includes(response.status);
          if (isRetryable && attempt <= this.#maxRetries) {
            // Full jitter exponential backoff: sleep between 0 and (2^attempt * base)
            const jitteredDelay = Math.random() * (delayMs * Math.pow(2, attempt));
            await new Promise((resolve) => setTimeout(resolve, jitteredDelay));
            continue;
          }

          let errorPayload: ProblemDetailsPayload;
          try {
            errorPayload = (await response.json()) as ProblemDetailsPayload;
          } catch {
            errorPayload = {
              type: "https://api.billing.example.com/errors/http_error",
              title: "HTTP Error",
              status: response.status,
              detail: response.statusText || "Unexpected network error",
              instance: path,
              code: "http_failure",
              retryable: isRetryable,
            };
          }
          throw new ProblemDetailsError(errorPayload);
        }

        return (await response.json()) as T;
      } catch (err: unknown) {
        if (err instanceof ProblemDetailsError) {
          throw err;
        }
        const isAbort = err instanceof DOMException && err.name === "TimeoutError";
        if (attempt <= this.#maxRetries) {
          const jitteredDelay = Math.random() * (delayMs * Math.pow(2, attempt));
          await new Promise((resolve) => setTimeout(resolve, jitteredDelay));
          continue;
        }
        throw new ProblemDetailsError({
          type: "https://api.billing.example.com/errors/network_failure",
          title: isAbort ? "Request Timeout" : "Network Transport Failure",
          status: isAbort ? 408 : 503,
          detail: err instanceof Error ? err.message : "Unknown network failure",
          instance: path,
          code: isAbort ? "timeout" : "network_unavailable",
          retryable: true,
          suggested_action: "Check connectivity and retry with exponential backoff.",
        });
      }
    }

    throw new ProblemDetailsError({
      type: "https://api.billing.example.com/errors/retry_exhaustion",
      title: "Retry Budget Exhausted",
      status: 504,
      detail: `Exhausted ${this.#maxRetries} retry attempts without successful response`,
      instance: path,
      code: "retries_exhausted",
      retryable: false,
    });
  }
}

// --- Top-Level Unified SDK Entry Point ---
export class BillingClient {
  readonly #httpClient: ResilientHttpClient;
  readonly paymentIntents: PaymentIntentsResource;
  readonly raw: ResilientHttpClient;

  constructor(options: ClientOptions) {
    this.#httpClient = new ResilientHttpClient(options);
    this.paymentIntents = new PaymentIntentsResource(this.#httpClient);
    this.raw = this.#httpClient; // Tier 3 escape hatch
  }
}

// --- Tier 3 Fluent Builder ---
export class BillingClientBuilder {
  #apiKey?: ApiKey;
  #baseUrl?: string;
  #timeoutMs?: number;
  #maxRetries?: number;
  #fetcher?: typeof fetch;

  withApiKey(key: ApiKey): this {
    this.#apiKey = key;
    return this;
  }

  withBaseUrl(url: string): this {
    this.#baseUrl = url;
    return this;
  }

  withTimeout(ms: number): this {
    this.#timeoutMs = ms;
    return this;
  }

  withMaxRetries(retries: number): this {
    this.#maxRetries = retries;
    return this;
  }

  withFetcher(fetcher: typeof fetch): this {
    this.#fetcher = fetcher;
    return this;
  }

  build(): BillingClient {
    if (!this.#apiKey) {
      throw new Error("Cannot build BillingClient: apiKey is required.");
    }
    return new BillingClient({
      apiKey: this.#apiKey,
      baseUrl: this.#baseUrl,
      defaultTimeoutMs: this.#timeoutMs,
      maxRetries: this.#maxRetries,
      fetcher: this.#fetcher,
    });
  }
}

// --- Self-Verification Suite (Runs on Direct Execution) ---
if (import.meta.main) {
  // 1. Verify Nominal Branded Types
  const customerId = asCustomerId("cus_99812401");
  const apiKey = asApiKey("sk_test_51Abc123");
  const currency = asCurrencyCode("usd");
  const idemKey = asIdempotencyKey("req_uniq_01");

  if (!customerId.startsWith("cus_")) throw new Error("CustomerId assertion failed");
  if (!apiKey.startsWith("sk_")) throw new Error("ApiKey assertion failed");
  if (currency !== "USD") throw new Error("CurrencyCode normalization failed");

  // 2. Verify Discriminated Union States
  const succeededIntent: PaymentIntent = {
    status: "succeeded",
    id: asPaymentIntentId("pi_12345"),
    amount: 5000,
    currency,
    chargeId: "ch_9988",
    completedAt: new Date().toISOString(),
  };

  const describeIntent = (intent: PaymentIntent): string => {
    switch (intent.status) {
      case "requires_payment_method":
        return `Awaiting payment method (${intent.clientSecret})`;
      case "requires_confirmation":
        return `Awaiting confirmation for ${intent.paymentMethodId}`;
      case "succeeded":
        return `Paid ${intent.amount} ${intent.currency} via ${intent.chargeId}`;
      case "canceled":
        return `Canceled: ${intent.cancellationReason}`;
      default:
        return assertNever(intent);
    }
  };

  const description = describeIntent(succeededIntent);
  if (!description.includes("Paid 5000 USD")) {
    throw new Error(`Discriminated union assertion failed: ${description}`);
  }

  // 3. Verify RFC 9457 Problem Details Serialization
  const problem = new ProblemDetailsError({
    type: "https://api.billing.example.com/errors/card_declined",
    title: "Card Declined",
    status: 402,
    detail: "The customer card has insufficient funds.",
    instance: "/v1/payment_intents/pi_12345/confirm",
    code: "insufficient_funds",
    retryable: false,
    suggested_action: "Prompt user for alternate payment method.",
  });

  const serialized = problem.toJSON();
  if (serialized.code !== "insufficient_funds" || serialized.status !== 402) {
    throw new Error("ProblemDetails serialization failed");
  }

  // 4. Verify Progressive Disclosure: Fluent Builder & Client
  const client = new BillingClientBuilder()
    .withApiKey(apiKey)
    .withTimeout(5_000)
    .withMaxRetries(2)
    .build();

  if (!(client.paymentIntents instanceof PaymentIntentsResource)) {
    throw new Error("Client initialization failed: paymentIntents resource missing");
  }

  console.log("✔ Hardened SDK Contract self-verification passed successfully!");
}

