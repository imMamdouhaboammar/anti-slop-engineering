//go:build unix

package main

import "syscall"

const evidenceOpenFlags = syscall.O_NONBLOCK | syscall.O_NOFOLLOW
