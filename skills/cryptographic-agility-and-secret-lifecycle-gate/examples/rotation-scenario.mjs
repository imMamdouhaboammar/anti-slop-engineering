export function observeNonce(seen, keyIdentity, nonce) {
  const nonces = seen.get(keyIdentity) ?? new Set()
  if (nonces.has(nonce)) throw new Error('NONCE_REPEATED')
  nonces.add(nonce)
  seen.set(keyIdentity, nonces)
}

export function exerciseRotation(sensitive) {
  const active = new Set(['v1', 'v2'])
  const logs = []
  let writeVersion = 'v1'
  let keyServiceAvailable = true

  function useVersion({ operation, version }) {
    let reason
    if (!keyServiceAvailable) reason = 'KEY_SERVICE_UNAVAILABLE'
    else if (!active.has(version)) reason = 'VERSION_REVOKED'
    else if (operation === 'write' && version !== writeVersion) reason = 'WRITE_VERSION_INACTIVE'

    if (reason) logs.push({ operation, version, reason })
    return { operation, version, allowed: !reason }
  }

  const legacyRead = { operation: 'read', version: 'v1' }
  const newRead = { operation: 'read', version: 'v2', sensitive }
  const legacyWrite = { operation: 'write', version: 'v1' }
  const events = [useVersion(legacyWrite), useVersion(legacyRead)]
  writeVersion = 'v2'
  events.push(useVersion({ operation: 'write', version: 'v2' }), useVersion(legacyRead), useVersion(legacyWrite))
  keyServiceAvailable = false
  events.push(useVersion(newRead))
  keyServiceAvailable = true
  active.delete('v1')
  events.push(useVersion(legacyRead), useVersion(newRead))
  return { events, logs }
}
