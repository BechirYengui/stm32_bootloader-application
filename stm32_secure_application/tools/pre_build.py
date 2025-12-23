#!/usr/bin/env python3
"""
============================================================================
Pre-Build Script - Vérifications Avant Compilation
============================================================================

Ce script s'exécute AVANT la compilation PlatformIO.
Il vérifie que tout est en ordre avant de compiler.
"""

import os
import sys
import re

# Import PlatformIO environment
try:
    Import("env")
except:
    # Fallback si exécuté en dehors de PlatformIO
    env = None

def check_vtor_configuration():
    """
    Vérifie que SCB->VTOR = 0x08002000 est présent dans main.c
    """
    print("\n[Pre-Build] Vérification de la configuration VTOR...")
    
    # Trouve le répertoire du projet
    if env:
        project_dir = env['PROJECT_DIR']
    else:
        project_dir = os.getcwd()
    
    main_c_path = os.path.join(project_dir, 'src', 'main.c')
    
    if not os.path.exists(main_c_path):
        print("⚠️  main.c non trouvé, ignoré")
        return True
    
    with open(main_c_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Cherche SCB->VTOR = 0x08002000
    vtor_pattern = r'SCB\s*->\s*VTOR\s*=\s*0x08002000'
    
    if re.search(vtor_pattern, content):
        print("✅ VTOR correctement configuré (0x08002000)")
        return True
    else:
        print("\n" + "="*70)
        print("⚠️  ATTENTION: VTOR non configuré !")
        print("="*70)
        print("\nAjoute cette ligne AU DÉBUT de main():")
        print("    SCB->VTOR = 0x08002000;")
        print("\nExemple:")
        print("    int main(void) {")
        print("        SCB->VTOR = 0x08002000;  // ← Ajoute ceci")
        print("        HAL_Init();")
        print("        // ... reste du code")
        print("    }")
        print("\nSans cela, l'application CRASHERA après le bootloader !")
        print("="*70 + "\n")
        
        return True  # Continue quand même (warning, pas erreur)

def check_signer_script():
    """
    Vérifie que firmware_signer.py existe
    """
    print("[Pre-Build] Vérification du script de signature...")
    
    if env:
        project_dir = env['PROJECT_DIR']
    else:
        project_dir = os.getcwd()
    
    signer_path = os.path.join(project_dir, 'tools', 'firmware_signer.py')
    
    if os.path.exists(signer_path):
        print("✅ firmware_signer.py trouvé")
        return True
    else:
        print("⚠️  firmware_signer.py manquant dans tools/")
        print("   La signature automatique ne fonctionnera pas")
        return False

def check_linker_script():
    """
    Vérifie que le linker script est configuré pour 0x08002000
    """
    print("[Pre-Build] Vérification du linker script...")
    
    if not env:
        print("⚠️  Environnement PlatformIO non disponible")
        return True
    
    ld_script = env.get('LDSCRIPT_PATH', '')
    
    if not ld_script or not os.path.exists(ld_script):
        # Essaie de trouver le linker script dans le projet
        project_dir = env['PROJECT_DIR']
        ld_candidates = [
            os.path.join(project_dir, 'STM32F103C8Tx_FLASH_APPLICATION.ld'),
            os.path.join(project_dir, 'STM32F103C8Tx_FLASH.ld'),
        ]
        
        for candidate in ld_candidates:
            if os.path.exists(candidate):
                ld_script = candidate
                break
        
        if not ld_script:
            print("⚠️  Linker script non trouvé")
            return True
    
    try:
        with open(ld_script, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Cherche ORIGIN = 0x08002000
        if '0x08002000' in content and 'FLASH' in content:
            print("✅ Linker script configuré pour 0x08002000")
            return True
        else:
            print("⚠️  Linker script ne semble pas configuré pour 0x08002000")
            print("   Vérifie STM32F103C8Tx_FLASH_APPLICATION.ld")
            return True
    except:
        print("⚠️  Impossible de lire le linker script")
        return True

def display_memory_info():
    """
    Affiche les informations mémoire
    """
    print("\n" + "="*70)
    print("📊 CONFIGURATION MÉMOIRE")
    print("="*70)
    print("Flash Application: 0x08002000 - 0x0800FFFF (48KB)")
    print("RAM:              0x20000000 - 0x20004FFF (20KB)")
    print("Bootloader:       0x08000000 - 0x08001FFF (8KB) - PROTECTED")
    print("="*70 + "\n")

def check_previous_build_size():
    """
    Vérifie la taille du dernier build
    """
    if not env:
        return
    
    build_dir = env['BUILD_DIR']
    firmware_bin = os.path.join(build_dir, 'firmware.bin')
    
    if os.path.exists(firmware_bin):
        size = os.path.getsize(firmware_bin)
        size_kb = size / 1024
        
        print(f"[Pre-Build] Dernier firmware: {size} bytes ({size_kb:.1f} KB)")
        
        if size > 48 * 1024:
            print("\n" + "="*70)
            print("⚠️  ATTENTION: Firmware > 48KB !")
            print("="*70)
            print(f"Taille actuelle: {size_kb:.1f} KB")
            print(f"Taille maximale: 48.0 KB")
            print(f"Dépassement:     {(size_kb - 48):.1f} KB")
            print("\nSolutions:")
            print("1. Active les optimisations: -Os -flto")
            print("2. Réduis la taille du code")
            print("3. Désactive les features non utilisées")
            print("="*70 + "\n")

def run_pre_build_checks():
    """
    Exécute toutes les vérifications
    """
    print("\n" + "🔍 "*35)
    print("PRE-BUILD CHECKS - Application Secure Boot")
    print("🔍 "*35 + "\n")
    
    # Affiche les infos mémoire
    display_memory_info()
    
    # Vérifications
    checks_passed = 0
    checks_total = 0
    
    checks = [
        ("VTOR Configuration", check_vtor_configuration),
        ("Firmware Signer", check_signer_script),
        ("Linker Script", check_linker_script),
    ]
    
    for name, check_func in checks:
        checks_total += 1
        try:
            if check_func():
                checks_passed += 1
        except Exception as e:
            print(f"⚠️  Erreur dans {name}: {e}")
    
    # Vérifie la taille du build précédent
    try:
        check_previous_build_size()
    except Exception as e:
        print(f"⚠️  Erreur vérification taille: {e}")
    
    print("\n" + "="*70)
    print(f"✅ Vérifications: {checks_passed}/{checks_total} OK")
    print("="*70 + "\n")
    
    if checks_passed < checks_total:
        print("⚠️  Certaines vérifications ont échoué")
        print("   La compilation continue, mais vérifie les warnings ci-dessus")
    
    print("🔨 Compilation en cours...\n")

# ============================================================================
# EXÉCUTION
# ============================================================================

if __name__ == "__main__":
    # Exécuté directement (test)
    run_pre_build_checks()
else:
    # Exécuté par PlatformIO
    if env:
        run_pre_build_checks()