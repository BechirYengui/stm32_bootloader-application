"""
Configuration pytest pour tests application
Fixtures réutilisables
"""

import pytest


# ============================================================================
# Fixture: Constantes Application
# ============================================================================

@pytest.fixture
def app_constants():
    """
    Constantes de l'application
    
    Usage:
        def test_vtor(app_constants):
            assert app_constants['APPLICATION_START'] == 0x08002000
    """
    return {
        # Flash
        'APPLICATION_START': 0x08002000,
        'APPLICATION_MAX_SIZE': 48 * 1024,  # 48KB
        'APPLICATION_END': 0x0800E000,
        
        # RAM
        'RAM_START': 0x20000000,
        'RAM_SIZE': 20 * 1024,  # 20KB
        'RAM_END': 0x20005000,
        
        # Bootloader
        'BOOTLOADER_START': 0x08000000,
        'BOOTLOADER_SIZE': 8 * 1024,  # 8KB
        
        # Metadata
        'METADATA_ADDR': 0x0800E000,
        'METADATA_SIZE': 8 * 1024,  # 8KB
        
        # VTOR
        'VTOR_REGISTER': 0xE000ED08,
        'VECT_TAB_OFFSET': 0x2000,
        
        # Flash Base
        'FLASH_BASE': 0x08000000,
    }


# ============================================================================
# Fixture: Configuration Linker
# ============================================================================

@pytest.fixture
def linker_config():
    """
    Configuration du linker script
    
    Usage:
        def test_flash(linker_config):
            assert linker_config['FLASH_ORIGIN'] == 0x08002000
    """
    return {
        'FLASH_ORIGIN': 0x08002000,
        'FLASH_LENGTH': 0xC000,  # 48KB
        'RAM_ORIGIN': 0x20000000,
        'RAM_LENGTH': 0x5000,    # 20KB
    }


# ============================================================================
# Fixture: Séquence Startup
# ============================================================================

@pytest.fixture
def startup_sequence():
    """
    Séquence correcte de démarrage
    
    Usage:
        def test_order(startup_sequence):
            assert startup_sequence[0] == 'VTOR'
    """
    return [
        'VTOR',              # 1. Configuration VTOR
        'DSB',               # 2. Data Synchronization Barrier
        'ISB',               # 3. Instruction Synchronization Barrier
        'HAL_Init',          # 4. HAL Initialization
        'SystemClock',       # 5. System Clock Configuration
        'Peripheral_Init',   # 6. Peripherals
        'Main_Loop'          # 7. Main loop
    ]


# ============================================================================
# Fixture: Vector Table
# ============================================================================

@pytest.fixture
def vector_table_info():
    """
    Informations sur la table des vecteurs
    
    Usage:
        def test_vectors(vector_table_info):
            assert vector_table_info['num_exceptions'] == 16
    """
    return {
        'num_exceptions': 16,      # Cortex-M3 exceptions
        'num_irq': 60,             # STM32F103 IRQ
        'total_vectors': 76,       # Total
        'min_size': 8,             # SP + Reset minimum
        'full_size': 76 * 4,       # 304 bytes
        'alignment': 128,          # Minimum alignment
    }


# ============================================================================
# Fixture: Memory Regions
# ============================================================================

@pytest.fixture
def memory_regions():
    """
    Régions mémoire du système
    
    Usage:
        def test_regions(memory_regions):
            bootloader = memory_regions['bootloader']
            assert bootloader['start'] == 0x08000000
    """
    return {
        'bootloader': {
            'start': 0x08000000,
            'size': 8 * 1024,
            'end': 0x08002000,
        },
        'application': {
            'start': 0x08002000,
            'size': 48 * 1024,
            'end': 0x0800E000,
        },
        'metadata': {
            'start': 0x0800E000,
            'size': 8 * 1024,
            'end': 0x08010000,
        },
        'ram': {
            'start': 0x20000000,
            'size': 20 * 1024,
            'end': 0x20005000,
        }
    }


# ============================================================================
# Helper Functions
# ============================================================================

def is_in_ram(address):
    """Vérifie si une adresse est en RAM"""
    return 0x20000000 <= address < 0x20005000


def is_in_flash(address):
    """Vérifie si une adresse est en Flash"""
    return 0x08000000 <= address < 0x08010000


def is_in_application_flash(address):
    """Vérifie si une adresse est dans la Flash application"""
    return 0x08002000 <= address < 0x0800E000


def has_thumb_bit(address):
    """Vérifie si une adresse a le Thumb bit (bit 0 = 1)"""
    return (address & 0x01) == 1
