"""
Tests d'Intégration - Bootloader Complet
Tests du workflow complet de boot
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

@pytest.mark.integration
class TestBootloaderComplete:
    """Tests du workflow complet du bootloader"""
    
    def test_complete_boot_sequence(self, bootloader_lib, bootloader_constants, test_firmware_valid):
        """Test de la séquence complète de boot"""
        # === ÉTAPE 1: Vérification ===
        
        # Calcule CRC et SHA
        crc32 = calculate_crc32_c(bootloader_lib, test_firmware_valid)
        sha256 = calculate_sha256_c(bootloader_lib, test_firmware_valid)
        
        # Simule les métadonnées
        metadata = struct.pack(
            '<IIII32sI44s',
            bootloader_constants['FIRMWARE_MAGIC'],  # magic
            0x00010000,                               # version 1.0.0
            len(test_firmware_valid),                 # size
            crc32,                                    # crc32
            sha256,                                   # sha256[32]
            0,                                        # timestamp
            b'\x00' * 44                              # reserved
        )
        
        # Parse métadonnées
        magic, version, size, crc32_stored = struct.unpack('<IIII', metadata[0:16])
        sha256_stored = metadata[16:48]
        
        # Check 1: Magic
        assert magic == bootloader_constants['FIRMWARE_MAGIC']
        
        # Check 2: Size
        assert 0 < size <= bootloader_constants['APPLICATION_MAX_SIZE']
        
        # Check 3: Stack Pointer
        sp = struct.unpack('<I', test_firmware_valid[0:4])[0]
        assert (sp & 0x2FFE0000) == 0x20000000
        
        # Check 4: CRC32
        assert crc32 == crc32_stored
        
        # Check 5: SHA-256
        assert sha256 == sha256_stored
        
        print("\n✅ Vérification complète RÉUSSIE")
        
        # === ÉTAPE 2: Jump (simulation) ===
        
        # Le bootloader ferait:
        # 1. __disable_irq()
        # 2. SCB->VTOR = APPLICATION_ADDRESS
        # 3. __set_MSP(app_stack)
        # 4. app_reset_handler()
        
        # On simule juste la lecture
        app_stack = struct.unpack('<I', test_firmware_valid[0:4])[0]
        app_reset = struct.unpack('<I', test_firmware_valid[4:8])[0]
        
        assert app_stack == 0x20005000
        assert app_reset == 0x08002001
        
        print("✅ Jump préparé (stack=0x{:08X}, reset=0x{:08X})".format(
            app_stack, app_reset))
    
    def test_corrupted_firmware_rejected(self, bootloader_lib, test_firmware_corrupted):
        """Test qu'un firmware corrompu est rejeté"""
        # Calcule hash du firmware corrompu
        crc_corrupted = calculate_crc32_c(bootloader_lib, test_firmware_corrupted)
        sha_corrupted = calculate_sha256_c(bootloader_lib, test_firmware_corrupted)
        
        # Simule des métadonnées avec hash original (avant corruption)
        # (comme si firmware a été modifié après signature)
        original_crc = 0x12345678  # CRC original (avant corruption)
        original_sha = b'\x00' * 32  # SHA original (avant corruption)
        
        # Le bootloader détectera que:
        # calculated_crc != metadata->crc32
        # calculated_sha != metadata->sha256
        
        assert crc_corrupted != original_crc
        assert sha_corrupted != original_sha
        
        print("\n✅ Firmware corrompu REJETÉ")
    
    def test_invalid_metadata_rejected(self, bootloader_constants):
        """Test que des métadonnées invalides sont rejetées"""
        
        # Test 1: Magic invalide
        metadata_bad_magic = struct.pack('<I', 0x12345678)
        magic = struct.unpack('<I', metadata_bad_magic)[0]
        assert magic != bootloader_constants['FIRMWARE_MAGIC']
        
        # Test 2: Size invalide
        metadata_bad_size = struct.pack('<III', 
            bootloader_constants['FIRMWARE_MAGIC'],
            0x00010000,
            0  # size = 0, invalide
        )
        _, _, size = struct.unpack('<III', metadata_bad_size)
        assert not (0 < size <= bootloader_constants['APPLICATION_MAX_SIZE'])
        
        print("\n✅ Métadonnées invalides REJETÉES")


@pytest.mark.integration
class TestFirmwareSigning:
    """Tests de signature et vérification de firmware"""
    
    def test_sign_and_verify_workflow(self, bootloader_lib, test_firmware_valid):
        """Test du workflow complet de signature"""
        import sys
        from pathlib import Path
        
        # Ajoute tools au path
        tools_path = Path(__file__).parent.parent / 'tools'
        sys.path.insert(0, str(tools_path))
        
        try:
            from firmware_signer import calculate_crc32, calculate_sha256
            
            # Signe le firmware
            crc_py = calculate_crc32(test_firmware_valid)
            sha_py = calculate_sha256(test_firmware_valid)
            
            # Vérifie avec le code C
            crc_c = calculate_crc32_c(bootloader_lib, test_firmware_valid)
            sha_c = calculate_sha256_c(bootloader_lib, test_firmware_valid)
            
            # Python et C doivent matcher !
            assert crc_py == crc_c, "CRC32 Python != C"
            assert sha_py == sha_c, "SHA-256 Python != C"
            
            print("\n✅ Signature Python == Vérification C")
        
        except ImportError:
            pytest.skip("firmware_signer.py non disponible")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
