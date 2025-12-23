#!/bin/bash
# ============================================================================
# secure_boot_deploy.sh - Workflow Complet Automatisé
# ============================================================================

set -e  # Arrête en cas d'erreur

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Chemins
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOOTLOADER_DIR="$(dirname "$SCRIPT_DIR")/stm32_secure_bootloader"
APPLICATION_DIR="$SCRIPT_DIR"

# ============================================================================
# FONCTIONS
# ============================================================================

print_header() {
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
}

print_step() {
    echo -e "${GREEN}▶ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✖ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# ============================================================================
# COMPILATION BOOTLOADER
# ============================================================================

compile_bootloader() {
    print_header "COMPILATION BOOTLOADER"
    
    cd "$BOOTLOADER_DIR"
    
    print_step "Nettoyage..."
    rm -rf .pio 2>/dev/null || true
    
    print_step "Compilation..."
    python3 -m platformio run -e bootloader
    
    if [ -f ".pio/build/bootloader/firmware.bin" ]; then
        local size=$(stat -f%z ".pio/build/bootloader/firmware.bin" 2>/dev/null || stat -c%s ".pio/build/bootloader/firmware.bin")
        print_success "Bootloader compilé ($size bytes)"
    else
        print_error "Échec compilation bootloader"
        exit 1
    fi
}

# ============================================================================
# COMPILATION APPLICATION
# ============================================================================

compile_application() {
    print_header "COMPILATION APPLICATION"
    
    cd "$APPLICATION_DIR"
    
    print_step "Nettoyage..."
    rm -rf .pio 2>/dev/null || true
    rm -f firmware_signed.bin 2>/dev/null || true
    
    print_step "Compilation..."
    python3 -m platformio run -e application
    
    if [ ! -f ".pio/build/application/firmware.bin" ]; then
        print_error "Échec compilation application"
        exit 1
    fi
    
    local size=$(stat -f%z ".pio/build/application/firmware.bin" 2>/dev/null || stat -c%s ".pio/build/application/firmware.bin")
    print_success "Application compilée ($size bytes)"
}

# ============================================================================
# SIGNATURE FIRMWARE
# ============================================================================

sign_firmware() {
    print_header "SIGNATURE FIRMWARE"
    
    cd "$APPLICATION_DIR"
    
    if [ ! -f "tools/firmware_signer.py" ]; then
        print_error "firmware_signer.py introuvable"
        exit 1
    fi
    
    if [ ! -f ".pio/build/application/firmware.bin" ]; then
        print_error "firmware.bin introuvable - compile d'abord"
        exit 1
    fi
    
    print_step "Signature en cours..."
    python3 tools/firmware_signer.py \
        .pio/build/application/firmware.bin \
        -o firmware_signed.bin \
        -v "${FIRMWARE_VERSION:-1.0.0}"
    
    if [ ! -f "firmware_signed.bin" ]; then
        print_error "Échec signature"
        exit 1
    fi
    
    local size=$(stat -f%z "firmware_signed.bin" 2>/dev/null || stat -c%s "firmware_signed.bin")
    print_success "Firmware signé ($size bytes)"
    
    # Vérifie les métadonnées
    print_step "Vérification métadonnées..."
    if command -v hexdump &> /dev/null; then
        local magic=$(hexdump -s 57600 -n 4 -e '4/1 "%02x"' firmware_signed.bin 2>/dev/null || echo "")
        if [ "$magic" = "deadbeef" ]; then
            print_success "Magic number OK (0xDEADBEEF)"
        else
            print_warning "Magic number: 0x$magic (attendu: 0xdeadbeef)"
        fi
    fi
}

# ============================================================================
# FLASH BOOTLOADER
# ============================================================================

flash_bootloader() {
    print_header "FLASH BOOTLOADER"
    
    cd "$BOOTLOADER_DIR"
    
    if [ ! -f ".pio/build/bootloader/firmware.bin" ]; then
        print_error "Bootloader non compilé"
        exit 1
    fi
    
    print_step "Flash @ 0x08000000..."
    st-flash write .pio/build/bootloader/firmware.bin 0x08000000
    
    if [ $? -eq 0 ]; then
        print_success "Bootloader flashé"
    else
        print_error "Échec flash bootloader"
        exit 1
    fi
}

# ============================================================================
# FLASH APPLICATION
# ============================================================================

flash_application() {
    print_header "FLASH APPLICATION"
    
    cd "$APPLICATION_DIR"
    
    if [ ! -f "firmware_signed.bin" ]; then
        print_error "firmware_signed.bin introuvable"
        exit 1
    fi
    
    print_step "Flash @ 0x08002000..."
    st-flash write firmware_signed.bin 0x08002000
    
    if [ $? -eq 0 ]; then
        print_success "Application flashée"
    else
        print_error "Échec flash application"
        exit 1
    fi
}

# ============================================================================
# EFFACEMENT COMPLET
# ============================================================================

erase_flash() {
    print_header "EFFACEMENT FLASH"
    
    print_step "Effacement en cours..."
    st-flash erase
    
    if [ $? -eq 0 ]; then
        print_success "Flash effacée"
    else
        print_error "Échec effacement"
        exit 1
    fi
}

# ============================================================================
# RESET
# ============================================================================

reset_device() {
    print_header "RESET DEVICE"
    
    print_step "Reset..."
    st-flash reset 2>/dev/null || true
    print_success "Reset effectué (ou déconnecté - reset manuel)"
}

# ============================================================================
# WORKFLOW COMPLET
# ============================================================================

deploy_all() {
    print_header "DÉPLOIEMENT COMPLET"
    echo ""
    
    # Vérifications
    if ! command -v st-flash &> /dev/null; then
        print_error "st-flash non installé"
        echo "Installe avec: sudo apt install stlink-tools"
        exit 1
    fi
    
    if ! command -v python3 &> /dev/null; then
        print_error "python3 non installé"
        exit 1
    fi
    
    # Vérifie ST-Link
    print_step "Vérification ST-Link..."
    if ! st-info --probe &> /dev/null; then
        print_warning "ST-Link non détecté - branche-le et réessaie"
        exit 1
    fi
    print_success "ST-Link détecté"
    echo ""
    
    # Workflow
    erase_flash
    echo ""
    
    compile_bootloader
    echo ""
    
    compile_application
    echo ""
    
    sign_firmware
    echo ""
    
    flash_bootloader
    echo ""
    
    flash_application
    echo ""
    
    reset_device
    echo ""
    
    # Résumé
    print_header "DÉPLOIEMENT TERMINÉ"
    echo ""
    echo -e "${GREEN}✓ Bootloader @ 0x08000000${NC}"
    echo -e "${GREEN}✓ Application @ 0x08002000 (signée)${NC}"
    echo ""
    echo -e "${YELLOW}Séquence LED attendue:${NC}"
    echo "  1. 2 blinks rapides → Bootloader démarre"
    echo "  2. 3 blinks lents   → Vérification OK"
    echo "  3. 3 blinks rapides → Application démarre"
    echo "  4. LED éteinte      → Terminé"
    echo ""
}

# ============================================================================
# MENU PRINCIPAL
# ============================================================================

show_menu() {
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  Secure Boot - Deployment Tool${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
    echo "1) Déploiement complet (tout automatique)"
    echo "2) Compiler bootloader uniquement"
    echo "3) Compiler + signer application"
    echo "4) Flash bootloader"
    echo "5) Flash application"
    echo "6) Effacer flash complète"
    echo "7) Reset device"
    echo "8) Workflow application (compile + signe + flash)"
    echo "9) Quitter"
    echo ""
}

# ============================================================================
# MAIN
# ============================================================================

main() {
    # Si arguments fournis
    case "$1" in
        all|deploy)
            deploy_all
            ;;
        bootloader|b)
            compile_bootloader
            ;;
        application|a)
            compile_application
            ;;
        sign|s)
            sign_firmware
            ;;
        flash-bootloader|fb)
            flash_bootloader
            ;;
        flash-app|fa)
            flash_application
            ;;
        erase|e)
            erase_flash
            ;;
        reset|r)
            reset_device
            ;;
        app-workflow|aw)
            compile_application
            echo ""
            sign_firmware
            echo ""
            flash_application
            echo ""
            reset_device
            ;;
        help|h)
            echo "Usage: $0 [commande]"
            echo ""
            echo "Commandes:"
            echo "  all, deploy         Déploiement complet"
            echo "  bootloader, b       Compile bootloader"
            echo "  application, a      Compile application"
            echo "  sign, s             Signe firmware"
            echo "  flash-bootloader    Flash bootloader"
            echo "  flash-app           Flash application"
            echo "  erase, e            Efface flash"
            echo "  reset, r            Reset device"
            echo "  app-workflow, aw    Compile + signe + flash app"
            echo "  help, h             Affiche cette aide"
            echo ""
            echo "Sans argument: menu interactif"
            ;;
        *)
            # Menu interactif
            while true; do
                show_menu
                read -p "Choix: " choice
                echo ""
                
                case $choice in
                    1) deploy_all ;;
                    2) compile_bootloader ;;
                    3) compile_application && echo "" && sign_firmware ;;
                    4) flash_bootloader ;;
                    5) flash_application ;;
                    6) erase_flash ;;
                    7) reset_device ;;
                    8) compile_application && echo "" && sign_firmware && echo "" && flash_application && echo "" && reset_device ;;
                    9) echo "Bye!"; exit 0 ;;
                    *) print_error "Choix invalide" ;;
                esac
                
                echo ""
                read -p "Appuie sur Enter pour continuer..."
                clear
            done
            ;;
    esac
}

main "$@"