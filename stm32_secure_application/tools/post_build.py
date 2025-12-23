#!/usr/bin/env python3
"""
============================================================================
Post-Build Script - Signature Automatique du Firmware
Version Corrigée - Chemins Absolus
============================================================================
"""

import os
import subprocess
import sys

# Import PlatformIO environment
try:
    Import("env")
except:
    print("⚠️  Erreur: Ce script doit être exécuté par PlatformIO")
    sys.exit(1)

def sign_firmware_callback(source, target, env):
    """
    Callback exécuté après la compilation
    """
    
    # Chemins résolus
    project_dir = env['PROJECT_DIR']
    build_dir = env['BUILD_DIR']
    prog_name = env['PROGNAME']
    
    elf_path = str(target[0])
    bin_path = os.path.join(build_dir, "firmware.bin")
    signed_path = os.path.join(project_dir, "firmware_signed.bin")
    signer_script = os.path.join(project_dir, "tools", "firmware_signer.py")
    
    print("\n" + "="*70)
    print("🔐 POST-BUILD: Signature du firmware")
    print("="*70)
    
    # Étape 1: Convertit ELF en BIN
    print("\n[1/3] Conversion ELF → BIN...")
    
    # Utilise env.Command pour objcopy
    objcopy = os.path.join(
        env.PioPlatform().get_package_dir("toolchain-gccarmnoneeabi") or "",
        "bin",
        "arm-none-eabi-objcopy"
    )
    
    objcopy_cmd = [
        objcopy,
        "-O", "binary",
        elf_path,
        bin_path
    ]
    
    try:
        result = subprocess.run(objcopy_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Erreur lors de la conversion:")
            print(result.stderr)
            print("\n⚠️  Le .bin sera créé par PlatformIO après ce script")
            print(f"⚠️  Utilise manuellement: python3 tools/firmware_signer.py .pio/build/{env['PIOENV']}/firmware.bin -o firmware_signed.bin -v 1.0.0")
            return
        
        print(f"✅ Firmware binaire créé: {bin_path}")
        
        # Vérifie la taille
        if os.path.exists(bin_path):
            bin_size = os.path.getsize(bin_path)
            print(f"   Taille: {bin_size} bytes ({bin_size/1024:.1f} KB)")
            
            if bin_size > 48 * 1024:
                print(f"⚠️  ATTENTION: Firmware > 48KB (limite: 48KB)")
                print(f"   Le bootloader occupe 8KB, il reste 48KB pour l'application")
    
    except Exception as e:
        print(f"❌ Erreur lors de la conversion: {e}")
        print("\n⚠️  Le .bin sera créé par PlatformIO")
        print(f"⚠️  Signe-le manuellement après compilation:")
        print(f"   python3 tools/firmware_signer.py .pio/build/{env['PIOENV']}/firmware.bin -o firmware_signed.bin -v 1.0.0")
        return
    
    # Étape 2: Vérifie que le script de signature existe
    print(f"\n[2/3] Vérification du script de signature...")
    
    if not os.path.exists(signer_script):
        print(f"❌ Script de signature introuvable: {signer_script}")
        print(f"   Télécharge firmware_signer.py dans tools/")
        return
    
    print(f"✅ Script trouvé: {signer_script}")
    
    # Attends que le fichier soit bien fermé
    import time
    time.sleep(0.1)
    
    # Vérifie que le fichier existe
    if not os.path.exists(bin_path):
        print(f"⚠️  Le fichier {bin_path} n'existe pas encore")
        print(f"   PlatformIO le créera après ce script")
        print(f"\n⚠️  Signe-le manuellement:")
        print(f"   python3 tools/firmware_signer.py .pio/build/{env['PIOENV']}/firmware.bin -o firmware_signed.bin -v 1.0.0")
        return
    
    # Étape 3: Signe le firmware
    print(f"\n[3/3] Signature du firmware...")
    
    sign_cmd = [
        sys.executable,
        signer_script,
        bin_path,
        "-o", signed_path,
        "-v", "1.0.0"
    ]
    
    try:
        result = subprocess.run(sign_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Erreur lors de la signature:")
            print(result.stderr)
            if result.stdout:
                print("Output:")
                print(result.stdout)
            return
        
        # Affiche l'output du script de signature
        if result.stdout:
            print(result.stdout)
        
        # Vérifie que le fichier signé existe
        if os.path.exists(signed_path):
            signed_size = os.path.getsize(signed_path)
            print(f"\n✅ Firmware signé créé: {signed_path}")
            print(f"   Taille: {signed_size} bytes ({signed_size/1024:.1f} KB)")
            
            print("\n" + "="*70)
            print("🎉 SIGNATURE RÉUSSIE !")
            print("="*70)
            print("\nProchaine étape:")
            print(f"  st-flash write firmware_signed.bin 0x08002000")
            print("\nOu avec OpenOCD:")
            print(f"  openocd -f interface/stlink.cfg -f target/stm32f1x.cfg \\")
            print(f"      -c \"init\" \\")
            print(f"      -c \"reset halt\" \\")
            print(f"      -c \"flash write_image erase firmware_signed.bin 0x08002000\" \\")
            print(f"      -c \"reset run\" \\")
            print(f"      -c \"shutdown\"")
            print("\n" + "="*70 + "\n")
        else:
            print(f"❌ Fichier signé non créé: {signed_path}")
    
    except Exception as e:
        print(f"❌ Erreur lors de la signature: {e}")
        import traceback
        traceback.print_exc()

# Ajoute le callback post-build
env.AddPostAction("$BUILD_DIR/${PROGNAME}.elf", sign_firmware_callback)

print("\n📌 Script post-build activé: signature automatique après compilation")