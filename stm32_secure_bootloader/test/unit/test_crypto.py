"""
Tests Unitaires - Fonctions Crypto
Tests du VRAI code C de lib/crypto/crypto_light.c
"""

import pytest
import hashlib


@pytest.mark.unit
@pytest.mark.crypto
class TestCRC32:
    """Tests de la fonction Calculate_CRC32 du bootloader"""
    
    def calculate_crc32(self, bootloader_lib, data: bytes) -> int:
        """Helper: Appelle la fonction C Calculate_CRC32"""
        from conftest import bytes_to_c_array
        data_array = bytes_to_c_array(data)
        return bootloader_lib.Calculate_CRC32(data_array, len(data))
    
    def test_crc32_ieee_vector(self, bootloader_lib):
        """Test avec vecteur IEEE 802.3 standard"""
        data = b'123456789'
        result = self.calculate_crc32(bootloader_lib, data)
        assert result == 0xCBF43926
    
    def test_crc32_empty(self, bootloader_lib):
        """Test avec données vides"""
        data = b''
        result = self.calculate_crc32(bootloader_lib, data)
        assert result == 0x00000000
    
    def test_crc32_hello(self, bootloader_lib):
        """Test avec 'hello'"""
        data = b'hello'
        result = self.calculate_crc32(bootloader_lib, data)
        assert result == 0x3610A686
    
    def test_crc32_firmware_size(self, bootloader_lib):
        """Test avec données taille firmware (10KB)"""
        data = b'F' * (10 * 1024)
        result = self.calculate_crc32(bootloader_lib, data)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFFFFFF
    
    def test_crc32_deterministic(self, bootloader_lib):
        """Test que CRC32 est déterministe"""
        data = b'deterministic_test'
        result1 = self.calculate_crc32(bootloader_lib, data)
        result2 = self.calculate_crc32(bootloader_lib, data)
        assert result1 == result2
    
    def test_crc32_detects_single_byte_change(self, bootloader_lib):
        """Test que CRC32 détecte un changement d'un seul byte"""
        data1 = b'original_data'
        data2 = b'original_datX'  # Dernier caractère changé
        
        crc1 = self.calculate_crc32(bootloader_lib, data1)
        crc2 = self.calculate_crc32(bootloader_lib, data2)
        
        assert crc1 != crc2


@pytest.mark.unit
@pytest.mark.crypto
class TestSHA256:
    """Tests de la fonction sha256_hash du bootloader"""
    
    def calculate_sha256(self, bootloader_lib, data: bytes) -> bytes:
        """Helper: Appelle la fonction C sha256_hash"""
        import ctypes
        from conftest import bytes_to_c_array
        
        data_array = bytes_to_c_array(data)
        hash_array = (ctypes.c_uint8 * 32)()
        
        bootloader_lib.sha256_hash(data_array, len(data), hash_array)
        
        return bytes(hash_array)
    
    def test_sha256_nist_abc(self, bootloader_lib):
        """Test avec vecteur NIST FIPS 180-4: 'abc'"""
        data = b'abc'
        result = self.calculate_sha256(bootloader_lib, data)
        
        # Vecteur NIST officiel
        expected = bytes.fromhex(
            'ba7816bf8f01cfea414140de5dae2223'
            'b00361a396177a9cb410ff61f20015ad'
        )
        
        assert result == expected
    
    def test_sha256_empty(self, bootloader_lib):
        """Test avec données vides"""
        data = b''
        result = self.calculate_sha256(bootloader_lib, data)
        
        expected = bytes.fromhex(
            'e3b0c44298fc1c149afbf4c8996fb924'
            '27ae41e4649b934ca495991b7852b855'
        )
        
        assert result == expected
    
    def test_sha256_nist_long(self, bootloader_lib):
        """Test avec vecteur NIST long"""
        data = b'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq'
        result = self.calculate_sha256(bootloader_lib, data)
        
        expected = bytes.fromhex(
            '248d6a61d20638b8e5c026930c3e6039'
            'a33ce45964ff2167f6ecedd419db06c1'
        )
        
        assert result == expected
    
    def test_sha256_matches_python_hashlib(self, bootloader_lib):
        """Test que SHA-256 C == SHA-256 Python"""
        data = b'test_comparison_with_python_hashlib'
        
        # Notre implémentation C
        result_c = self.calculate_sha256(bootloader_lib, data)
        
        # hashlib Python
        result_py = hashlib.sha256(data).digest()
        
        assert result_c == result_py
    
    def test_sha256_firmware_size(self, bootloader_lib):
        """Test avec données taille firmware (48KB)"""
        data = b'L' * (48 * 1024)
        result = self.calculate_sha256(bootloader_lib, data)
        
        assert len(result) == 32
        
        # Vérifie contre Python
        expected = hashlib.sha256(data).digest()
        assert result == expected
    
    @pytest.mark.slow
    def test_sha256_detects_single_bit_change(self, bootloader_lib):
        """Test que SHA-256 change complètement avec 1 bit modifié"""
        data1 = b'firmware_original_data'
        data2 = bytearray(data1)
        data2[0] ^= 0x01  # Flip 1 bit
        data2 = bytes(data2)
        
        hash1 = self.calculate_sha256(bootloader_lib, data1)
        hash2 = self.calculate_sha256(bootloader_lib, data2)
        
        # Les hashs doivent être complètement différents
        assert hash1 != hash2
        
        # Compte les bytes différents (devrait être ~16 sur 32)
        diff_count = sum(a != b for a, b in zip(hash1, hash2))
        assert diff_count > 10


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
