import assert from 'node:assert/strict'
import { createCipheriv, createDecipheriv } from 'node:crypto'
import test from 'node:test'
import { exerciseRotation, observeNonce } from './rotation-scenario.mjs'

const fromHex = (value) => Buffer.from(value.replaceAll(' ', ''), 'hex')

// Public NIST GCM-AES128 example 2. These inputs are test vectors.
const vector = {
  material: fromHex('FEFFE992 8665731C 6D6A8F94 67308308'),
  nonce: fromHex('CAFEBABE FACEDBAD DECAF888'),
  plaintext: fromHex('D9313225 F88406E5 A55909C5 AFF5269A 86A7A953 1534F7DA 2E4C303D 8A318A72'
    + ' 1C3C0C95 95680953 2FCF0E24 49A6B525 B16AEDF5 AA0DE657 BA637B39 1AAFD255'),
  ciphertext: fromHex('42831EC2 21777424 4B7221B7 84D0D49C E3AA212F 2C02A4E0 35C17E23 29ACA12E'
    + ' 21D514B2 5466931C 7D8F6A5A AC84AA05 1BA30B39 6A0AAC97 3D58E091 473F5985'),
  tag: fromHex('4D5C2AF3 27CD64A6 2CF35ABD 2BA6FAB4'),
}

test('built-in AES-GCM matches the public known-answer vector', () => {
  const cipher = createCipheriv('aes-128-gcm', vector.material, vector.nonce, { authTagLength: 16 })
  const ciphertext = Buffer.concat([cipher.update(vector.plaintext), cipher.final()])
  assert.deepEqual(ciphertext, vector.ciphertext)
  assert.deepEqual(cipher.getAuthTag(), vector.tag)
})

test('the built-in reader authenticates ciphertext before returning verified bytes', () => {
  const decipher = createDecipheriv('aes-128-gcm', vector.material, vector.nonce, { authTagLength: 16 })
  decipher.setAuthTag(vector.tag)
  assert.deepEqual(Buffer.concat([decipher.update(vector.ciphertext), decipher.final()]), vector.plaintext)
  const corruptedTag = Buffer.from(vector.tag)
  corruptedTag[0] ^= 1
  const invalid = createDecipheriv('aes-128-gcm', vector.material, vector.nonce, { authTagLength: 16 })
  invalid.setAuthTag(corruptedTag)
  assert.throws(() => Buffer.concat([invalid.update(vector.ciphertext), invalid.final()]))
})

test('the fixture rejects duplicate nonce evidence for the same data-key identity', () => {
  const seen = new Map()
  observeNonce(seen, 'data-v1', 'nonce-1')
  assert.throws(() => observeNonce(seen, 'data-v1', 'nonce-1'), /NONCE_REPEATED/)
  observeNonce(seen, 'data-v2', 'nonce-1')
})

test('rotation keeps authorized legacy reads, blocks revoked keys, and emits safe logs on failure', () => {
  const sensitive = 'fixture-marker-never-log'
  const { events, logs } = exerciseRotation(sensitive)
  assert.deepEqual(events, [
    { operation: 'write', version: 'v1', allowed: true },
    { operation: 'read', version: 'v1', allowed: true },
    { operation: 'write', version: 'v2', allowed: true },
    { operation: 'read', version: 'v1', allowed: true },
    { operation: 'write', version: 'v1', allowed: false },
    { operation: 'read', version: 'v2', allowed: false },
    { operation: 'read', version: 'v1', allowed: false },
    { operation: 'read', version: 'v2', allowed: true },
  ])
  assert.deepEqual(logs.map(({ reason }) => reason), ['WRITE_VERSION_INACTIVE', 'KEY_SERVICE_UNAVAILABLE', 'VERSION_REVOKED'])
  assert.ok(!JSON.stringify(logs).includes(sensitive))
  assert.ok(logs.every((event) => Object.keys(event).sort().join(',') === 'operation,reason,version'))
})
