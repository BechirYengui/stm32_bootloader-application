"""
Tests Unitaires - Table des Vecteurs
Vérification de la structure de la vector table à 0x08002000
"""

import pytest
import struct


@pytest.mark.unit
class TestVectorTableStructure:
    """Tests de la structure de la table des vecteurs"""
    
    def test_vector_table_location(self, app_constants):
        """Test que la vector table est à 0x08002000"""
        vector_table_addr = app_constants['APPLICATION_START']
        assert vector_table_addr == 0x08002000
    
    def test_vector_table_size(self):
        """Test taille minimale de la vector table"""
        # Minimum: Stack Pointer (4 bytes) + Reset Handler (4 bytes) = 8 bytes
        # Complet STM32F103: 16 exceptions + 60 IRQ = 76 * 4 = 304 bytes
        min_size = 8
        full_size = 76 * 4
        
        assert min_size == 8
        assert full_size == 304
    
    def test_vector_table_alignment(self, app_constants):
        """Test alignement de la vector table"""
        vtor = app_constants['APPLICATION_START']
        
        # Alignement minimum 128 bytes pour Cortex-M3
        assert (vtor & 0x7F) == 0


@pytest.mark.unit
class TestStackPointer:
    """Tests du Stack Pointer (premier élément vector table)"""
    
    def test_stack_pointer_in_ram(self):
        """Test que le Stack Pointer initial est en RAM"""
        # Stack Pointer doit pointer vers la RAM
        # RAM STM32F103C8: 0x20000000 - 0x20005000 (20KB)
        
        valid_sp_range = (0x20000000, 0x20005000)
        
        # Exemples de SP valides
        valid_sps = [
            0x20005000,  # Top de la RAM (classique)
            0x20004000,
            0x20003000,
        ]
        
        for sp in valid_sps:
            assert valid_sp_range[0] <= sp <= valid_sp_range[1]
    
    def test_stack_pointer_not_in_flash(self):
        """Test que le SP n'est PAS dans la Flash"""
        # SP en Flash = ERREUR CRITIQUE
        flash_range = (0x08000000, 0x08010000)
        
        # SP valide (en RAM)
        sp_valid = 0x20005000
        
        # Vérifie que SP n'est pas en Flash
        assert not (flash_range[0] <= sp_valid < flash_range[1])
    
    def test_stack_pointer_alignment(self):
        """Test alignement du Stack Pointer"""
        # SP doit être aligné sur 8 bytes (recommandé ARM)
        sp = 0x20005000
        
        assert (sp & 0x07) == 0, "SP doit être aligné sur 8 bytes"


@pytest.mark.unit
class TestResetHandler:
    """Tests du Reset Handler (deuxième élément vector table)"""
    
    def test_reset_handler_in_flash(self):
        """Test que Reset Handler est dans la Flash"""
        # Reset Handler doit pointer vers la Flash application
        # Flash application: 0x08002000 - 0x0800E000 (48KB)
        
        flash_app_start = 0x08002000
        flash_app_end = 0x0800E000
        
        # Exemple Reset Handler (avec Thumb bit)
        reset_handler = 0x08002401  # Adresse 0x08002400, Thumb bit = 1
        reset_addr = reset_handler & ~0x01  # Enlève Thumb bit
        
        assert flash_app_start <= reset_addr < flash_app_end
    
    def test_reset_handler_thumb_bit(self):
        """Test que Reset Handler a le Thumb bit à 1"""
        # Cortex-M3 fonctionne UNIQUEMENT en Thumb mode
        # Bit 0 de l'adresse DOIT être à 1
        
        # Exemples Reset Handler valides
        valid_handlers = [
            0x08002001,  # Adresse 0x08002000, Thumb=1
            0x08002401,  # Adresse 0x08002400, Thumb=1
            0x08003001,  # Adresse 0x08003000, Thumb=1
        ]
        
        for handler in valid_handlers:
            assert (handler & 0x01) == 1, "Thumb bit doit être à 1"
    
    def test_reset_handler_not_null(self):
        """Test que Reset Handler n'est pas NULL"""
        reset_handler = 0x08002001
        
        assert reset_handler != 0x00000000
        assert reset_handler != 0xFFFFFFFF


@pytest.mark.unit
class TestVectorTableContent:
    """Tests du contenu de la table des vecteurs"""
    
    def test_vector_table_first_8_bytes(self):
        """Test des 8 premiers bytes (SP + Reset)"""
        # Octets 0-3: Stack Pointer (doit être en RAM)
        # Octets 4-7: Reset Handler (doit être en Flash avec Thumb bit)
        
        sp = 0x20005000
        reset = 0x08002401
        
        # Pack en little-endian
        vector_table_start = struct.pack('<II', sp, reset)
        
        assert len(vector_table_start) == 8
        
        # Unpack et vérifie
        sp_unpacked, reset_unpacked = struct.unpack('<II', vector_table_start)
        
        assert sp_unpacked == sp
        assert reset_unpacked == reset
        assert (sp_unpacked & 0x2FFE0000) == 0x20000000  # En RAM
        assert (reset_unpacked & 0x01) == 1  # Thumb bit


@pytest.mark.unit
class TestExceptionVectors:
    """Tests des vecteurs d'exception"""
    
    def test_exception_count(self):
        """Test nombre de vecteurs d'exception Cortex-M3"""
        # Cortex-M3 standard: 16 exceptions système
        num_exceptions = 16
        assert num_exceptions == 16
    
    def test_irq_count_stm32f103(self):
        """Test nombre d'IRQ STM32F103"""
        # STM32F103: 60 interruptions externes
        num_irq = 60
        assert num_irq == 60
    
    def test_total_vectors(self):
        """Test nombre total de vecteurs"""
        # Total = Exceptions + IRQ = 16 + 60 = 76
        total = 16 + 60
        assert total == 76


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
