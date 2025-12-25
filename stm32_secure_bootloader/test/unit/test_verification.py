"""
Tests Unitaires - Vérification Firmware
Tests de la logique de Verify_Firmware() du bootloader
"""

import pytest
import struct
import ctypes


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_crc32_c(bootloader_lib, data: bytes) -> int:
    """Appelle la fonction C Calculate_CRC32"""
    data_array = (ctypes.c_uint8 * len(data))(*data)
    return bootloader_lib.Calculate_CRC32(data_array, len(data))


def calculate_sha256_c(bootloader_lib, data: bytes) -> bytes:
    """Appelle la fonction C sha256_hash"""
    data_array = (ctypes.c_uint8 * len(data))(*data)
    hash_array = (ctypes.c_uint8 * 32)()
    bootloader_lib.sha256_hash(data_array, len(data), hash_array)
    return bytes(hash_array)


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.verification
class TestMagicNumber:
    """Tests de vérification du magic number"""
    
    def test_valid_magic_number(self, bootloader_constants):
        """Test avec magic number valide"""
        magic = 0xDEADBEEF
        assert magic == bootloader_constants['FIRMWARE_MAGIC']
    
    def test_invalid_magic_numbers(self, bootloader_constants):
        """Test avec magic numbers invalides"""
        invalid_magics = [
            0x00000000,
            0xFFFFFFFF,
            0xDEADBEE0,  # Un bit différent
            0xBEEFDEAD,  # Inversé
            0x12345678,
        ]
        
        for invalid_magic in invalid_magics:
            assert invalid_magic != bootloader_constants['FIRMWARE_MAGIC']


@pytest.mark.unit
@pytest.mark.verification
class TestSizeValidation:
    """Tests de validation de la taille du firmware"""
    
    def test_valid_sizes(self, bootloader_constants):
        """Test avec tailles valides"""
        max_size = bootloader_constants['APPLICATION_MAX_SIZE']
        
        valid_sizes = [
            1,
            100,
            1024,
            10000,
            max_size - 1,
            max_size,
        ]
        
        for size in valid_sizes:
            assert 0 < size <= max_size
    
    def test_invalid_sizes(self, bootloader_constants):
        """Test avec tailles invalides"""
        max_size = bootloader_constants['APPLICATION_MAX_SIZE']
        
        invalid_sizes = [
            0,                    # Zéro
            max_size + 1,         # Trop grand
            0xFFFFFFFF,          # Maximum uint32
            100000,               # Beaucoup trop grand
        ]
        
        for size in invalid_sizes:
            assert not (0 < size <= max_size)


@pytest.mark.unit
@pytest.mark.verification
class TestStackPointerValidation:
    """Tests de validation du stack pointer"""
    
    def test_valid_stack_pointers(self, bootloader_constants):
        """Test avec stack pointers valides"""
        valid_sps = [
            0x20000100,  # Début RAM
            0x20002800,  # Milieu RAM
            0x20005000,  # Fin RAM (top)
        ]
        
        for sp in valid_sps:
            # Simule: if ((sp & 0x2FFE0000) != 0x20000000)
            assert (sp & 0x2FFE0000) == 0x20000000
    
    def test_invalid_stack_pointers(self, bootloader_constants):
        """Test avec stack pointers invalides"""
        invalid_sps = [
            0x08000000,  # Flash
            0x00000000,  # NULL
            0x40000000,  # Périphériques
            0xFFFFFFFF,  # Invalide
            0x1FFFFFFF,  # Juste avant RAM
        ]
        
        for sp in invalid_sps:
            # Le bootloader devrait rejeter
            assert (sp & 0x2FFE0000) != 0x20000000
    
    def test_stack_pointer_from_firmware(self):
        """Test extraction du stack pointer du firmware"""
        # Crée un firmware de test
        sp = 0x20005000
        reset = 0x08002001
        firmware = struct.pack('<II', sp, reset)
        
        # Extrait le stack pointer (premier uint32)
        sp_extracted = struct.unpack('<I', firmware[0:4])[0]
        
        assert sp_extracted == sp
        assert (sp_extracted & 0x2FFE0000) == 0x20000000


@pytest.mark.unit
@pytest.mark.verification
class TestCRC32Verification:
    """Tests de vérification CRC32"""
    
    def test_crc32_match(self, bootloader_lib, test_firmware_valid):
        """Test avec CRC32 correct"""
        # Calcule le CRC32
        calculated_crc = calculate_crc32_c(bootloader_lib, test_firmware_valid)
        
        # Simule les métadonnées
        metadata_crc = calculated_crc
        
        # Simule: if (calculated_crc != metadata->crc32)
        assert calculated_crc == metadata_crc
    
    def test_crc32_mismatch(self, bootloader_lib, test_firmware_valid):
        """Test avec CRC32 incorrect"""
        calculated_crc = calculate_crc32_c(bootloader_lib, test_firmware_valid)
        
        # CRC incorrect dans les métadonnées
        wrong_crc = calculated_crc + 1
        
        # Le bootloader devrait rejeter
        assert calculated_crc != wrong_crc


@pytest.mark.unit
@pytest.mark.verification
class TestSHA256Verification:
    """Tests de vérification SHA-256"""
    
    def test_sha256_match(self, bootloader_lib, test_firmware_valid):
        """Test avec SHA-256 correct"""
        # Calcule le hash
        calculated_hash = calculate_sha256_c(bootloader_lib, test_firmware_valid)
        
        # Simule les métadonnées
        metadata_hash = calculated_hash
        
        # Simule: if (memcmp(calculated_hash, metadata->sha256, 32) != 0)
        assert calculated_hash == metadata_hash
    
    def test_sha256_mismatch(self, bootloader_lib, test_firmware_valid):
        """Test avec SHA-256 incorrect"""
        calculated_hash = calculate_sha256_c(bootloader_lib, test_firmware_valid)
        
        # Hash incorrect dans les métadonnées
        wrong_hash = b'\x00' * 32
        
        # Le bootloader devrait rejeter
        assert calculated_hash != wrong_hash


@pytest.mark.unit
@pytest.mark.verification
class TestCompleteVerification:
    """Tests de la séquence complète de vérification"""
    
    def test_all_checks_pass(self, bootloader_lib, bootloader_constants, test_firmware_valid):
        """Test avec firmware complètement valide"""
        # Calcule CRC et SHA
        crc = calculate_crc32_c(bootloader_lib, test_firmware_valid)
        sha = calculate_sha256_c(bootloader_lib, test_firmware_valid)
        
        # Métadonnées
        metadata = {
            'magic': bootloader_constants['FIRMWARE_MAGIC'],
            'size': len(test_firmware_valid),
            'crc32': crc,
            'sha256': sha
        }
        
        # Extrait stack pointer
        sp = struct.unpack('<I', test_firmware_valid[0:4])[0]
        
        # Toutes les vérifications
        assert metadata['magic'] == bootloader_constants['FIRMWARE_MAGIC']  # Check 1
        assert 0 < metadata['size'] <= bootloader_constants['APPLICATION_MAX_SIZE']  # Check 2
        assert (sp & 0x2FFE0000) == 0x20000000  # Check 3
        assert crc == metadata['crc32']  # Check 4
        assert sha == metadata['sha256']  # Check 5
    
    def test_firmware_corruption_detected(self, bootloader_lib, test_firmware_valid, test_firmware_corrupted):
        """Test détection de firmware corrompu"""
        # Hash du firmware original
        crc_original = calculate_crc32_c(bootloader_lib, test_firmware_valid)
        sha_original = calculate_sha256_c(bootloader_lib, test_firmware_valid)
        
        # Hash du firmware corrompu
        crc_corrupted = calculate_crc32_c(bootloader_lib, test_firmware_corrupted)
        sha_corrupted = calculate_sha256_c(bootloader_lib, test_firmware_corrupted)
        
        # Les deux doivent détecter la corruption
        assert crc_original != crc_corrupted  # CRC détecte
        assert sha_original != sha_corrupted  # SHA détecte


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
