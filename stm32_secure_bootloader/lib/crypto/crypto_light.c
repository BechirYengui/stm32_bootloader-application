/**
 * ============================================================================
 * IMPLÉMENTATION CRYPTO LÉGÈRE POUR STM32 BARE METAL
 * ============================================================================
 */

#include "crypto_light.h"

// ============================================================================
// SHA-256 Implementation (Optimisée pour ARM Cortex-M3)
// ============================================================================

#define ROTLEFT(a,b) (((a) << (b)) | ((a) >> (32-(b))))
#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))

#define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

static const uint32_t k[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

static void sha256_transform(SHA256_CTX *ctx, const uint8_t data[]) {
    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];
    
    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
    for (; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];
    
    a = ctx->state[0];
    b = ctx->state[1];
    c = ctx->state[2];
    d = ctx->state[3];
    e = ctx->state[4];
    f = ctx->state[5];
    g = ctx->state[6];
    h = ctx->state[7];
    
    for (i = 0; i < 64; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + k[i] + m[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    
    ctx->state[0] += a;
    ctx->state[1] += b;
    ctx->state[2] += c;
    ctx->state[3] += d;
    ctx->state[4] += e;
    ctx->state[5] += f;
    ctx->state[6] += g;
    ctx->state[7] += h;
}

void sha256_init(SHA256_CTX *ctx) {
    ctx->count[0] = 0;
    ctx->count[1] = 0;
    ctx->state[0] = 0x6a09e667;
    ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372;
    ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f;
    ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab;
    ctx->state[7] = 0x5be0cd19;
}

void sha256_update(SHA256_CTX *ctx, const uint8_t *data, size_t len) {
    uint32_t i;
    
    for (i = 0; i < len; ++i) {
        ctx->buffer[ctx->count[0]] = data[i];
        ctx->count[0]++;
        if (ctx->count[0] == 64) {
            sha256_transform(ctx, ctx->buffer);
            ctx->count[1]++;
            ctx->count[0] = 0;
        }
    }
}

void sha256_final(SHA256_CTX *ctx, uint8_t hash[32]) {
    uint32_t i;
    
    i = ctx->count[0];
    
    if (ctx->count[0] < 56) {
        ctx->buffer[i++] = 0x80;
        while (i < 56)
            ctx->buffer[i++] = 0x00;
    }
    else {
        ctx->buffer[i++] = 0x80;
        while (i < 64)
            ctx->buffer[i++] = 0x00;
        sha256_transform(ctx, ctx->buffer);
        memset(ctx->buffer, 0, 56);
    }
    
    uint64_t bitlen = (ctx->count[1] * 512) + (ctx->count[0] * 8);
    ctx->buffer[63] = bitlen;
    ctx->buffer[62] = bitlen >> 8;
    ctx->buffer[61] = bitlen >> 16;
    ctx->buffer[60] = bitlen >> 24;
    ctx->buffer[59] = bitlen >> 32;
    ctx->buffer[58] = bitlen >> 40;
    ctx->buffer[57] = bitlen >> 48;
    ctx->buffer[56] = bitlen >> 56;
    sha256_transform(ctx, ctx->buffer);
    
    for (i = 0; i < 4; ++i) {
        hash[i]      = (ctx->state[0] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 4]  = (ctx->state[1] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 8]  = (ctx->state[2] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 12] = (ctx->state[3] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 16] = (ctx->state[4] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 20] = (ctx->state[5] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 24] = (ctx->state[6] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 28] = (ctx->state[7] >> (24 - i * 8)) & 0x000000ff;
    }
}

void sha256_hash(const uint8_t *data, size_t len, uint8_t hash[32]) {
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, data, len);
    sha256_final(&ctx, hash);
}

// ============================================================================
// HMAC-SHA256
// ============================================================================

void hmac_sha256(const uint8_t *key, size_t key_len,
                 const uint8_t *data, size_t data_len,
                 uint8_t hmac[32]) {
    uint8_t k_pad[64];
    uint8_t tk[32];
    SHA256_CTX ctx;
    
    // Si la clé est trop longue, hash-la
    if (key_len > 64) {
        sha256_hash(key, key_len, tk);
        key = tk;
        key_len = 32;
    }
    
    // Prépare k_pad
    memset(k_pad, 0, sizeof(k_pad));
    memcpy(k_pad, key, key_len);
    
    // HMAC = H((K ⊕ opad) || H((K ⊕ ipad) || message))
    
    // Inner hash: H((K ⊕ ipad) || message)
    for (int i = 0; i < 64; i++)
        k_pad[i] ^= 0x36;
    
    sha256_init(&ctx);
    sha256_update(&ctx, k_pad, 64);
    sha256_update(&ctx, data, data_len);
    sha256_final(&ctx, hmac);
    
    // Outer hash: H((K ⊕ opad) || inner_hash)
    memset(k_pad, 0, sizeof(k_pad));
    memcpy(k_pad, key, key_len);
    
    for (int i = 0; i < 64; i++)
        k_pad[i] ^= 0x5c;
    
    sha256_init(&ctx);
    sha256_update(&ctx, k_pad, 64);
    sha256_update(&ctx, hmac, 32);
    sha256_final(&ctx, hmac);
}

// ============================================================================
// XOR Cipher (Chiffrement simple et rapide)
// ============================================================================

void xor_cipher_encrypt(uint8_t *data, size_t data_len,
                       const uint8_t *key, size_t key_len) {
    for (size_t i = 0; i < data_len; i++) {
        data[i] ^= key[i % key_len];
    }
}

void xor_cipher_decrypt(uint8_t *data, size_t data_len,
                       const uint8_t *key, size_t key_len) {
    // XOR est symétrique
    xor_cipher_encrypt(data, data_len, key, key_len);
}

// ============================================================================
// Base64 Encoding/Decoding
// ============================================================================

static const char base64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

size_t base64_encode(const uint8_t *src, size_t src_len, char *dst) {
    size_t i, j;
    for (i = 0, j = 0; i < src_len; ) {
        uint32_t octet_a = i < src_len ? src[i++] : 0;
        uint32_t octet_b = i < src_len ? src[i++] : 0;
        uint32_t octet_c = i < src_len ? src[i++] : 0;
        
        uint32_t triple = (octet_a << 16) + (octet_b << 8) + octet_c;
        
        dst[j++] = base64_table[(triple >> 18) & 0x3F];
        dst[j++] = base64_table[(triple >> 12) & 0x3F];
        dst[j++] = base64_table[(triple >> 6) & 0x3F];
        dst[j++] = base64_table[triple & 0x3F];
    }
    
    // Padding
    int mod = src_len % 3;
    if (mod == 1) {
        dst[j - 2] = '=';
        dst[j - 1] = '=';
    } else if (mod == 2) {
        dst[j - 1] = '=';
    }
    
    dst[j] = '\0';
    return j;
}

size_t base64_decode(const char *src, uint8_t *dst, size_t dst_len) {
    size_t i, j;
    uint8_t dtable[256];
    
    memset(dtable, 0x80, 256);
    for (i = 0; i < sizeof(base64_table) - 1; i++)
        dtable[(uint8_t)base64_table[i]] = i;
    dtable['='] = 0;
    
    size_t src_len = strlen(src);
    for (i = 0, j = 0; i < src_len && j < dst_len; ) {
        uint32_t sextet_a = dtable[(uint8_t)src[i++]];
        uint32_t sextet_b = dtable[(uint8_t)src[i++]];
        uint32_t sextet_c = dtable[(uint8_t)src[i++]];
        uint32_t sextet_d = dtable[(uint8_t)src[i++]];
        
        uint32_t triple = (sextet_a << 18) + (sextet_b << 12) + (sextet_c << 6) + sextet_d;
        
        if (j < dst_len) dst[j++] = (triple >> 16) & 0xFF;
        if (j < dst_len) dst[j++] = (triple >> 8) & 0xFF;
        if (j < dst_len) dst[j++] = triple & 0xFF;
    }
    
    return j;
}

// ============================================================================
// RNG (utilise le bruit ADC comme source d'entropie)
// ============================================================================

static uint32_t rng_state = 0xDEADBEEF;

void crypto_random_init(uint16_t adc_seed) {
    rng_state = (adc_seed << 16) | (HAL_GetTick() & 0xFFFF);
}

uint32_t crypto_random_get(void) {
    // Linear Congruential Generator (simple mais suffisant pour démo)
    rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF;
    return rng_state;
}

void crypto_random_bytes(uint8_t *buffer, size_t len) {
    for (size_t i = 0; i < len; i++) {
        if (i % 4 == 0) {
            uint32_t rand = crypto_random_get();
            buffer[i] = (rand >> 24) & 0xFF;
            buffer[i+1] = (rand >> 16) & 0xFF;
            buffer[i+2] = (rand >> 8) & 0xFF;
            buffer[i+3] = rand & 0xFF;
        }
    }
}
