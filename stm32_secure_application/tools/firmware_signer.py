#!/usr/bin/env python3
"""
============================================================================
FIRMWARE SIGNER - Outil pour Signer et Packager le Firmware STM32
============================================================================

Usage:
    python firmware_signer.py firmware.bin -o firmware_signed.bin

Génère:
    - firmware_signed.bin : Firmware + Metadata + Signature
    - firmware.sha256     : Hash SHA-256
    - metadata.json       : Métadonnées lisibles

Exemple:
    python firmware_signer.py build/firmware.bin -o signed_firmware.bin
============================================================================
"""

import hashlib
import struct
import time
import argparse
import json
import os
from pathlib import Path

# ============================================================================
# CONSTANTES
# ============================================================================

FIRMWARE_MAGIC = 0xDEADBEEF
MAX_FIRMWARE_SIZE = 48 * 1024  # 48KB
METADATA_SIZE = 128  # bytes
SIGNATURE_SIZE = 256  # bytes (pour RSA-2048 ou placeholder)

# ============================================================================
# CRC32
# ============================================================================

def calculate_crc32(data):
    """Calcule le CRC32 (polynomial IEEE 802.3)"""
    crc = 0xFFFFFFFF
    
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    
    return (~crc) & 0xFFFFFFFF

# ============================================================================
# SHA-256
# ============================================================================

def calculate_sha256(data):
    """Calcule le SHA-256"""
    return hashlib.sha256(data).digest()

# ============================================================================
# METADATA
# ============================================================================

def create_metadata(firmware_data, version="1.0.0"):
    """
    Crée la structure de métadonnées (128 bytes)
    
    typedef struct {
        uint32_t magic;              // FIRMWARE_MAGIC
        uint32_t version;            // Version (ex: 0x00010000 = v1.0.0)
        uint32_t size;               // Taille
        uint32_t crc32;              // CRC32
        uint8_t  sha256[32];         // SHA-256
        uint32_t timestamp;          // Unix timestamp
        uint8_t  reserved[44];       // Padding
    } FirmwareMetadata_t;
    """
    
    # Parse version (ex: "1.2.3" → 0x00010203)
    version_parts = version.split('.')
    version_int = (int(version_parts[0]) << 16) | \
                  (int(version_parts[1]) << 8) | \
                  int(version_parts[2])
    
    # Calcule CRC32 et SHA-256
    crc32 = calculate_crc32(firmware_data)
    sha256 = calculate_sha256(firmware_data)
    
    # Timestamp actuel
    timestamp = int(time.time())
    
    # Pack la structure (little-endian)
    metadata = struct.pack(
        '<I I I I 32s I 44s',
        FIRMWARE_MAGIC,      # magic
        version_int,         # version
        len(firmware_data),  # size
        crc32,               # crc32
        sha256,              # sha256[32]
        timestamp,           # timestamp
        b'\x00' * 44         # reserved
    )
    
    return metadata, crc32, sha256, timestamp

# ============================================================================
# SIGNATURE (Placeholder pour démo)
# ============================================================================

def create_signature(firmware_data):
    """
    Crée une signature "placeholder" pour démo
    
    En production:
        1. Utiliser RSA-2048 ou ECDSA-256
        2. Signer avec clé privée
        3. Stocker uniquement la clé publique dans le STM32
    
    Pour démo:
        - Double SHA-256 comme "signature"
    """
    
    # Double hash comme signature simplifiée
    hash1 = hashlib.sha256(firmware_data).digest()
    hash2 = hashlib.sha256(hash1).digest()
    
    # Pad à 256 bytes (taille RSA-2048)
    signature = hash2 + (b'\x00' * (SIGNATURE_SIZE - len(hash2)))
    
    return signature

# ============================================================================
# PACKAGER
# ============================================================================

def package_firmware(firmware_path, output_path, version="1.0.0"):
    """
    Package le firmware avec métadonnées et signature
    
    Layout final:
    [Firmware] [Metadata 128B] [Signature 256B] [Reference Hash 32B]
    """
    
    print(f"[+] Reading firmware: {firmware_path}")
    
    # Lit le firmware
    with open(firmware_path, 'rb') as f:
        firmware_data = f.read()
    
    # Vérifie la taille
    if len(firmware_data) > MAX_FIRMWARE_SIZE:
        print(f"[!] ERROR: Firmware too large ({len(firmware_data)} bytes > {MAX_FIRMWARE_SIZE} bytes)")
        return False
    
    print(f"[+] Firmware size: {len(firmware_data)} bytes")
    
    # Pad le firmware à 48KB
    firmware_padded = firmware_data + (b'\xFF' * (MAX_FIRMWARE_SIZE - len(firmware_data)))
    
    # Crée les métadonnées
    print(f"[+] Creating metadata (version {version})...")
    metadata, crc32, sha256, timestamp = create_metadata(firmware_data, version)
    
    print(f"    CRC32:     0x{crc32:08X}")
    print(f"    SHA-256:   {sha256.hex()}")
    print(f"    Timestamp: {timestamp} ({time.ctime(timestamp)})")
    
    # Crée la signature
    print(f"[+] Creating signature...")
    signature = create_signature(firmware_data)
    
    # Reference hash (pour vérification bootloader)
    reference_hash = sha256 + (b'\x00' * (32))  # Pad à 64 bytes si besoin
    
    # Package tout ensemble
    final_package = firmware_padded + metadata + signature + reference_hash
    
    # Écrit le package
    print(f"[+] Writing signed firmware: {output_path}")
    with open(output_path, 'wb') as f:
        f.write(final_package)
    
    # Sauvegarde les infos
    metadata_json = {
        "magic": f"0x{FIRMWARE_MAGIC:08X}",
        "version": version,
        "size": len(firmware_data),
        "crc32": f"0x{crc32:08X}",
        "sha256": sha256.hex(),
        "timestamp": timestamp,
        "timestamp_human": time.ctime(timestamp),
        "signature_type": "double-sha256 (demo)",
        "total_size": len(final_package)
    }
    
    json_path = output_path.replace('.bin', '_metadata.json')
    with open(json_path, 'w') as f:
        json.dump(metadata_json, f, indent=4)
    
    print(f"[+] Metadata saved: {json_path}")
    
    # Sauvegarde le hash seul
    hash_path = output_path.replace('.bin', '.sha256')
    with open(hash_path, 'w') as f:
        f.write(sha256.hex())
    
    print(f"[+] SHA-256 saved: {hash_path}")
    
    print(f"\n[✓] Firmware signed successfully!")
    print(f"    Total size: {len(final_package)} bytes")
    print(f"    Ready to flash at 0x08002000")
    
    return True

# ============================================================================
# VÉRIFICATION
# ============================================================================

def verify_firmware(signed_firmware_path):
    """Vérifie un firmware signé"""
    
    print(f"[+] Verifying firmware: {signed_firmware_path}")
    
    with open(signed_firmware_path, 'rb') as f:
        data = f.read()
    
    # Extrait les composants
    firmware = data[0:MAX_FIRMWARE_SIZE]
    metadata_bytes = data[MAX_FIRMWARE_SIZE:MAX_FIRMWARE_SIZE + METADATA_SIZE]
    signature = data[MAX_FIRMWARE_SIZE + METADATA_SIZE:MAX_FIRMWARE_SIZE + METADATA_SIZE + SIGNATURE_SIZE]
    reference_hash = data[MAX_FIRMWARE_SIZE + METADATA_SIZE + SIGNATURE_SIZE:MAX_FIRMWARE_SIZE + METADATA_SIZE + SIGNATURE_SIZE + 32]
    
    # Parse metadata
    unpacked = struct.unpack('<I I I I 32s I 44s', metadata_bytes)
    magic, version, size, crc32_stored, sha256_stored, timestamp, _ = unpacked
    
    # Vérifie magic
    if magic != FIRMWARE_MAGIC:
        print(f"[!] INVALID MAGIC: 0x{magic:08X} (expected 0x{FIRMWARE_MAGIC:08X})")
        return False
    
    print(f"[✓] Magic OK")
    
    # Vérifie taille
    firmware_actual = firmware[0:size]
    
    # Recalcule CRC32
    crc32_calc = calculate_crc32(firmware_actual)
    if crc32_calc != crc32_stored:
        print(f"[!] CRC32 MISMATCH: 0x{crc32_calc:08X} != 0x{crc32_stored:08X}")
        return False
    
    print(f"[✓] CRC32 OK: 0x{crc32_calc:08X}")
    
    # Recalcule SHA-256
    sha256_calc = calculate_sha256(firmware_actual)
    if sha256_calc != sha256_stored:
        print(f"[!] SHA-256 MISMATCH")
        print(f"    Calculated: {sha256_calc.hex()}")
        print(f"    Stored:     {sha256_stored.hex()}")
        return False
    
    print(f"[✓] SHA-256 OK: {sha256_calc.hex()}")
    
    # Vérifie signature
    signature_calc = create_signature(firmware_actual)
    if signature_calc != signature:
        print(f"[!] SIGNATURE MISMATCH")
        return False
    
    print(f"[✓] Signature OK")
    
    print(f"\n[✓✓✓] Firmware verification PASSED!")
    print(f"      Version: {(version >> 16) & 0xFF}.{(version >> 8) & 0xFF}.{version & 0xFF}")
    print(f"      Size: {size} bytes")
    print(f"      Timestamp: {time.ctime(timestamp)}")
    
    return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Sign and package STM32 firmware for Secure Boot'
    )
    
    parser.add_argument(
        'firmware',
        help='Input firmware binary (.bin)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='firmware_signed.bin',
        help='Output signed firmware (default: firmware_signed.bin)'
    )
    
    parser.add_argument(
        '-v', '--version',
        default='1.0.0',
        help='Firmware version (default: 1.0.0)'
    )
    
    parser.add_argument(
        '--verify',
        action='store_true',
        help='Verify an already signed firmware'
    )
    
    args = parser.parse_args()
    
    if args.verify:
        # Mode vérification
        success = verify_firmware(args.firmware)
        return 0 if success else 1
    else:
        # Mode signature
        success = package_firmware(args.firmware, args.output, args.version)
        return 0 if success else 1

if __name__ == '__main__':
    exit(main())
