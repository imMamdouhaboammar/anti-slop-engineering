export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat",     // New feature
        "fix",      // Bug fix
        "refactor", // Refactoring without logic change
        "perf",     // Performance improvement
        "test",     // Adding or updating tests
        "docs",     // Documentation updates
        "style",    // Formatting/code style only
        "build",    // Build scripts, dependencies, Docker, BUCK
        "ci",       // CI/CD pipelines, Lefthook, GitHub Actions
        "chore",    // Maintenance tasks
        "revert",   // Reverting previous commits
        "security"  // Security patches
      ]
    ],
    "scope-case": [2, "always", "kebab-case"],
    "subject-empty": [2, "never"],
    "subject-case": [0],
    "header-max-length": [2, "always", 100]
  }
};
