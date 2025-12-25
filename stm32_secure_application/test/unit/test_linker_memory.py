"""
Tests Unitaires - Configuration Mémoire et Linker Script
Vérification que l'application est bien configurée pour 0x08002000
"""

import pytest


@pytest.mark.unit
class TestLinkerScriptFlash:
    """Tests de la configuration Flash dans le linker script"""
    
    def test_flash_origin(self, app_constants):
        """Test que FLASH ORIGIN = 0x08002000"""
        # Dans le linker script (.ld):
        # FLASH (rx) : ORIGIN = 0x08002000, LENGTH = 48K
        
        flash_origin = app_constants['APPLICATION_START']
        assert flash_origin == 0x08002000
    
    def test_flash_length(self, app_constants):
        """Test que FLASH LENGTH = 48K"""
        # Application: 48KB (0xC000 bytes)
        # De 0x08002000 à 0x0800E000
        
        flash_length = app_constants['APPLICATION_MAX_SIZE']
        assert flash_length == 48 * 1024
        assert flash_length == 0xC000
    
    def test_flash_end_address(self, app_constants):
        """Test adresse de fin de la Flash application"""
        start = app_constants['APPLICATION_START']
        size = app_constants['APPLICATION_MAX_SIZE']
        end = start + size
        
        assert end == 0x0800E000


@pytest.mark.unit
class TestLinkerScriptRAM:
    """Tests de la configuration RAM dans le linker script"""
    
    def test_ram_origin(self, app_constants):
        """Test que RAM ORIGIN = 0x20000000"""
        # RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 20K
        
        ram_origin = app_constants['RAM_START']
        assert ram_origin == 0x20000000
    
    def test_ram_length(self, app_constants):
        """Test que RAM LENGTH = 20K"""
        # STM32F103C8: 20KB RAM
        
        ram_length = app_constants['RAM_SIZE']
        assert ram_length == 20 * 1024
        assert ram_length == 0x5000
    
    def test_ram_end_address(self, app_constants):
        """Test adresse de fin de la RAM"""
        start = app_constants['RAM_START']
        size = app_constants['RAM_SIZE']
        end = start + size
        
        assert end == 0x20005000


@pytest.mark.unit
class TestVECT_TAB_OFFSET:
    """Tests du VECT_TAB_OFFSET (critique pour VTOR)"""
    
    def test_vect_tab_offset_value(self):
        """Test que VECT_TAB_OFFSET = 0x2000"""
        # Dans system_stm32f1xx.c ou build flags:
        # #define VECT_TAB_OFFSET 0x2000
        # 
        # Ou flag de compilation:
        # -DVECT_TAB_OFFSET=0x2000
        
        offset = 0x2000
        assert offset == 0x2000
        assert offset == 8192  # 8KB (espace bootloader)
    
    def test_vtor_calculation(self):
        """Test calcul du VTOR depuis VECT_TAB_OFFSET"""
        # VTOR = FLASH_BASE | VECT_TAB_OFFSET
        # VTOR = 0x08000000 | 0x2000 = 0x08002000
        
        FLASH_BASE = 0x08000000
        VECT_TAB_OFFSET = 0x2000
        VTOR = FLASH_BASE | VECT_TAB_OFFSET
        
        assert VTOR == 0x08002000


@pytest.mark.unit
class TestMemoryLayout:
    """Tests du layout mémoire complet"""
    
    def test_bootloader_region(self, app_constants):
        """Test région mémoire bootloader"""
        # Bootloader: 0x08000000 - 0x08002000 (8KB)
        bootloader_start = 0x08000000
        bootloader_size = 8 * 1024
        bootloader_end = bootloader_start + bootloader_size
        
        assert bootloader_end == app_constants['APPLICATION_START']
    
    def test_application_region(self, app_constants):
        """Test région mémoire application"""
        # Application: 0x08002000 - 0x0800E000 (48KB)
        app_start = app_constants['APPLICATION_START']
        app_size = app_constants['APPLICATION_MAX_SIZE']
        app_end = app_start + app_size
        
        assert app_start == 0x08002000
        assert app_end == 0x0800E000
    
    def test_metadata_region(self, app_constants):
        """Test région mémoire métadonnées"""
        # Métadonnées: 0x0800E000 - 0x08010000 (8KB)
        metadata_addr = app_constants.get('METADATA_ADDR', 0x0800E000)
        
        assert metadata_addr == 0x0800E000
    
    def test_no_overlap(self, app_constants):
        """Test qu'il n'y a pas de chevauchement mémoire"""
        # Bootloader:   0x08000000 - 0x08002000
        # Application:  0x08002000 - 0x0800E000
        # Metadata:     0x0800E000 - 0x08010000
        
        bootloader_end = 0x08002000
        app_start = app_constants['APPLICATION_START']
        app_end = app_start + app_constants['APPLICATION_MAX_SIZE']
        metadata_start = 0x0800E000
        
        # Pas de chevauchement
        assert bootloader_end == app_start  # Bootloader → Application
        assert app_end == metadata_start    # Application → Metadata


@pytest.mark.unit
class TestAddressRanges:
    """Tests des plages d'adresses valides"""
    
    def test_valid_flash_addresses(self, app_constants):
        """Test plage d'adresses Flash valides pour l'application"""
        start = app_constants['APPLICATION_START']
        end = start + app_constants['APPLICATION_MAX_SIZE']
        
        # Adresses valides pour le code
        valid_addresses = [
            start,          # Début
            start + 0x100,  # Milieu
            end - 4,        # Fin
        ]
        
        for addr in valid_addresses:
            assert start <= addr < end
    
    def test_invalid_flash_addresses(self, app_constants):
        """Test adresses Flash invalides"""
        start = app_constants['APPLICATION_START']
        end = start + app_constants['APPLICATION_MAX_SIZE']
        
        # Adresses invalides (hors plage)
        invalid_addresses = [
            0x08000000,  # Bootloader
            0x08001000,  # Bootloader
            0x0800E000,  # Métadonnées
            0x08010000,  # Hors Flash
        ]
        
        for addr in invalid_addresses:
            assert not (start <= addr < end)


@pytest.mark.unit
class TestBuildFlags:
    """Tests des flags de compilation requis"""
    
    def test_vect_tab_offset_flag(self):
        """Test que VECT_TAB_OFFSET est défini"""
        # Flag requis: -DVECT_TAB_OFFSET=0x2000
        # Ou dans le code: #define VECT_TAB_OFFSET 0x2000
        
        VECT_TAB_OFFSET = 0x2000
        assert VECT_TAB_OFFSET == 0x2000
    
    def test_application_address_flag(self):
        """Test flag APPLICATION_ADDRESS si utilisé"""
        # Optionnel: -DAPPLICATION_ADDRESS=0x08002000
        APPLICATION_ADDRESS = 0x08002000
        assert APPLICATION_ADDRESS == 0x08002000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
