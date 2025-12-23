/**
 * ============================================================================
 * CRYPTO ULTRA-LÉGER POUR STM32 BARE METAL
 * ============================================================================
 * 
 * SHA-256: ~2KB Flash
 * HMAC: ~500 bytes Flash
 * XOR Cipher: ~100 bytes Flash
 * 
 * Pas de malloc, pas d'OS, pas de bibliothèque externe lourde
 * ============================================================================
 */

#ifndef CRYPTO_LIGHT_H
#define CRYPTO_LIGHT_H

#include <stdint.h>
#include <string.h>

// ============================================================================
// SHA-256 (Implémentation légère)
// ============================================================================

typedef struct {
    uint32_t state[8];
    uint32_t count[2];
    uint8_t buffer[64];
} SHA256_CTX;

void sha256_init(SHA256_CTX *ctx);
void sha256_update(SHA256_CTX *ctx, const uint8_t *data, size_t len);
void sha256_final(SHA256_CTX *ctx, uint8_t hash[32]);

// Helper: calcule SHA-256 en une seule fois
void sha256_hash(const uint8_t *data, size_t len, uint8_t hash[32]);

// ============================================================================
// HMAC-SHA256 (Authentification)
// ============================================================================

void hmac_sha256(const uint8_t *key, size_t key_len,
                 const uint8_t *data, size_t data_len,
                 uint8_t hmac[32]);

// ============================================================================
// XOR Cipher Simple (Chiffrement léger)
// ============================================================================

void xor_cipher_encrypt(uint8_t *data, size_t data_len,
                       const uint8_t *key, size_t key_len);

void xor_cipher_decrypt(uint8_t *data, size_t data_len,
                       const uint8_t *key, size_t key_len);

// ============================================================================
// Base64 (Pour transmission JSON)
// ============================================================================

size_t base64_encode(const uint8_t *src, size_t src_len, char *dst);
size_t base64_decode(const char *src, uint8_t *dst, size_t dst_len);

// ============================================================================
// Random Number Generator (utilise ADC noise)
// ============================================================================

void crypto_random_init(uint16_t adc_seed);
uint32_t crypto_random_get(void);
void crypto_random_bytes(uint8_t *buffer, size_t len);

#endif // CRYPTO_LIGHT_H
