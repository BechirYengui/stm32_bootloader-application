"""
Configuration pytest globale pour tests bootloader
Fixtures réutilisables pour tous les tests
"""

import pytest
import ctypes
from pathlib import Path


# ============================================================================
# Fixture: Bibliothèque Bootloader Compilée
# ============================================================================

@pytest.fixture(scope="session")
def bootloader_lib():
    """
    Charge la bibliothèque bootloader compilée (.so)
    
    Usage:
        def test_crc32(bootloader_lib):
            result = bootloader_lib.Calculate_CRC32(data, len(data))
    """
    lib_path = Path(__file__).parent / 'bindings' / 'libbootloader.so'
    
    if not lib_path.exists():
        pytest.skip(f"Bibliothèque non trouvée: {lib_path}")
    
    lib = ctypes.CDLL(str(lib_path))
    
    # Configure CRC32
    lib.Calculate_CRC32.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_uint32]
    lib.Calculate_CRC32.restype = ctypes.c_uint32
    
    # Configure SHA-256
    lib.sha256_hash.argtypes = [
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_uint8)
    ]
    lib.sha256_hash.restype = None
    
    return lib


# ============================================================================
# Fixture: Firmware de Test
# ============================================================================

@pytest.fixture
def test_firmware_valid():
    """
    Retourne un firmware de test valide
    
    Usage:
        def test_verify(test_firmware_valid):
            assert verify_firmware(test_firmware_valid)
    """
    import struct
    
    # Crée un firmware valide
    sp = 0x20005000  # Stack pointer en RAM
    reset = 0x08002001  # Reset vector avec Thumb bit
    
    firmware = struct.pack('<II', sp, reset)
    firmware += b'\x00' * 1000  # Code simulé
    
    return firmware


@pytest.fixture
def test_firmware_corrupted(test_firmware_valid):
    """
    Retourne un firmware corrompu
    
    Usage:
        def test_detect_corruption(test_firmware_corrupted):
            assert not verify_firmware(test_firmware_corrupted)
    """
    firmware = bytearray(test_firmware_valid)
    firmware[500] ^= 0xFF  # Corrompt 1 byte
    return bytes(firmware)


# ============================================================================
# Fixture: Métadonnées
# ============================================================================

@pytest.fixture
def valid_metadata():
    """
    Retourne des métadonnées valides
    
    Usage:
        def test_metadata(valid_metadata):
            assert valid_metadata['magic'] == 0xDEADBEEF
    """
    return {
        'magic': 0xDEADBEEF,
        'version': 0x00010203,  # 1.2.3
        'size': 1024,
        'crc32': 0x12345678,
        'sha256': b'\x00' * 32,
    }


# ============================================================================
# Fixture: Constantes Bootloader
# ============================================================================

@pytest.fixture
def bootloader_constants():
    """
    Constantes du bootloader
    
    Usage:
        def test_address(bootloader_constants):
            assert address == bootloader_constants['BOOTLOADER_START']
    """
    return {
        'BOOTLOADER_START': 0x08000000,
        'BOOTLOADER_SIZE': 8 * 1024,
        'APPLICATION_START': 0x08002000,
        'APPLICATION_MAX_SIZE': 48 * 1024,
        'METADATA_ADDR': 0x0800E000,
        'FIRMWARE_MAGIC': 0xDEADBEEF,
        'RAM_START': 0x20000000,
        'RAM_END': 0x20005000,
    }


# ============================================================================
# Helper Functions
# ============================================================================

def bytes_to_c_array(data: bytes):
    """Convertit bytes Python en tableau C uint8_t[]"""
    return (ctypes.c_uint8 * len(data))(*data)
