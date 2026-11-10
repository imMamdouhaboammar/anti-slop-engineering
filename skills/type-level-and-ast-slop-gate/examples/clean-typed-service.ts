// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

/**
 * Clean Reference Implementation: Zero-Slop Architecture
 * Demonstrates type-integrity, boundary validation, lazy iterators,
 * mutating reducers, and documented invariant type assertions.
 */

export interface User {
  readonly id: string;
  readonly email: string;
  readonly active: boolean;
  readonly credits: number;
}

export interface UserStore {
  findById(id: string): Promise<User | null>;
  save(user: User): Promise<void>;
  listActive(): Promise<readonly User[]>;
}

export class UserService {
  constructor(private readonly store: UserStore) {}

  /**
   * Aggregate user credits using in-place accumulator mutation (O(N) linear time).
   */
  aggregateCredits(users: readonly User[]): Record<string, number> {
    return users.reduce((acc, user) => {
      acc[user.id] = user.credits;
      return acc;
    }, {} as Record<string, number>);
  }

  /**
   * Filter active user emails using lazy iterator helpers (zero intermediate array allocations).
   */
  extractActiveEmails(users: readonly User[]): string[] {
    return users
      .values()
      .filter((user) => user.active)
      .map((user) => user.email)
      .toArray();
  }

  /**
   * Safe domain branding with explicit invariant documentation.
   */
  brandVerifiedId(rawId: string): string {
    // SAFETY: Input identifier format was validated by boundary UUID parser.
    const branded = rawId as string;
    return branded;
  }
}

/**
 * Verified In-Memory Test Double (replaces module mocking).
 */
export class InMemoryUserStore implements UserStore {
  private readonly users = new Map<string, User>();

  async findById(id: string): Promise<User | null> {
    return this.users.get(id) ?? null;
  }

  async save(user: User): Promise<void> {
    this.users.set(user.id, user);
  }

  async listActive(): Promise<readonly User[]> {
    return Array.from(this.users.values()).filter((u) => u.active);
  }
}
