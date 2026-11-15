//go:build unix

package main

import "syscall"

const auditSourceOpenFlags = syscall.O_NONBLOCK
