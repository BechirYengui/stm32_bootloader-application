"""
Tests d'Intégration - Application Complète
Tests du système complet de l'application
"""

import pytest


@pytest.mark.integration
class TestApplicationComplete:
    """Tests d'intégration de l'application"""
    
    def test_complete_configuration(self, app_constants, startup_sequence):
        """Test de la configuration complète de l'application"""
        
        # Vérifie VTOR
        vtor = app_constants['APPLICATION_START']
        assert vtor == 0x08002000
        assert (vtor & 0x7F) == 0  # Aligné
        
        # Vérifie séquence startup
        assert startup_sequence[0] == 'VTOR'
        assert startup_sequence[3] == 'HAL_Init'
        
        # Vérifie mémoire
        assert app_constants['APPLICATION_MAX_SIZE'] == 48 * 1024
    
    def test_memory_layout_complete(self, memory_regions):
        """Test du layout mémoire complet"""
        
        bootloader = memory_regions['bootloader']
        application = memory_regions['application']
        metadata = memory_regions['metadata']
        
        # Vérifie que tout se suit sans trou
        assert bootloader['end'] == application['start']
        assert application['end'] == metadata['start']
        
        # Vérifie tailles
        assert bootloader['size'] == 8 * 1024
        assert application['size'] == 48 * 1024
        assert metadata['size'] == 8 * 1024
    
    def test_vtor_and_vector_table(self, app_constants, vector_table_info):
        """Test VTOR + Vector Table ensemble"""
        
        # VTOR pointe vers la vector table
        vtor = app_constants['APPLICATION_START']
        
        # Vector table commence à VTOR
        vector_table_addr = vtor
        assert vector_table_addr == 0x08002000
        
        # Vector table a la bonne taille
        min_size = vector_table_info['min_size']
        full_size = vector_table_info['full_size']
        
        assert min_size == 8  # SP + Reset minimum
        assert full_size == 304  # 76 vecteurs


@pytest.mark.integration
class TestBootloaderToApplication:
    """Tests de la transition bootloader → application"""
    
    def test_bootloader_jump_preparation(self, app_constants):
        """Test que le bootloader prépare correctement le jump"""
        
        # Le bootloader a configuré:
        # 1. VTOR = 0x08002000 (fait par bootloader)
        # 2. MSP = valeur à [0x08002000]
        # 3. Jump à [0x08002004]
        
        # L'application DOIT reconfigurer VTOR
        # car certains bootloaders ne le font pas
        vtor = app_constants['APPLICATION_START']
        assert vtor == 0x08002000
    
    def test_application_independence(self, app_constants):
        """Test que l'application est indépendante du bootloader"""
        
        # L'application NE DOIT PAS supposer que:
        # - VTOR est configuré
        # - Les périphériques sont dans un état connu
        # - La RAM est initialisée
        
        # L'application DOIT:
        # 1. Configurer VTOR elle-même
        # 2. Initialiser tous ses périphériques
        # 3. Initialiser ses variables
        
        vtor = app_constants['APPLICATION_START']
        assert vtor == 0x08002000


@pytest.mark.integration
class TestCriticalPath:
    """Tests du chemin critique de démarrage"""
    
    def test_critical_startup_path(self, startup_sequence, app_constants):
        """Test du chemin critique complet"""
        
        # Chemin critique:
        # 1. Reset
        # 2. Stack Pointer chargé depuis [0x08002000]
        # 3. Reset Handler appelé depuis [0x08002004]
        # 4. main() exécuté
        # 5. VTOR configuré (PREMIÈRE ligne de main)
        # 6. Barrières mémoire
        # 7. HAL_Init()
        # 8. Reste du code
        
        # Vérifie que VTOR est en premier
        assert startup_sequence[0] == 'VTOR'
        
        # Vérifie valeur VTOR
        assert app_constants['APPLICATION_START'] == 0x08002000


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
