#!/bin/bash
# Script de compilation des bindings C pour les tests

set -e

echo "🔨 Compilation des bindings C du bootloader..."
echo ""

# Compile crypto_test.c en bibliothèque partagée
gcc -shared -fPIC -O2 \
    -DTEST_BUILD \
    -I../../lib/crypto \
    -o libbootloader.so \
    crypto_test.c \
    2>&1 | tee compile.log

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Compilation réussie!"
    echo "   Bibliothèque: libbootloader.so"
    ls -lh libbootloader.so
    
    # Test de chargement
    echo ""
    echo "🧪 Test de chargement..."
    python3 << 'EOF'
import ctypes
try:
    lib = ctypes.CDLL('./libbootloader.so')
    print("✅ Bibliothèque chargée avec succès")
    
    # Vérifie les fonctions
    lib.Calculate_CRC32
    lib.sha256_hash
    print("✅ Fonctions trouvées: Calculate_CRC32, sha256_hash")
except Exception as e:
    print(f"❌ Erreur: {e}")
    exit(1)
EOF
    
    echo ""
    echo "✅ Bindings prêts pour les tests!"
else
    echo ""
    echo "❌ Erreur de compilation"
    cat compile.log
    exit 1
fi
