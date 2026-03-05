#!/bin/bash
# Ce script force Ollama à libérer la VRAM de votre GPU utilisée par les modèles du projet RAG.
# Il envoie la commande keep_alive=0 pour décharger qwen3.5:9b et nomic-embed-text.

echo "🔗 Déchargement des modèles Ollama pour libérer la VRAM..."
curl -s http://localhost:11434/api/generate -d '{"model": "qwen3.5:9b", "keep_alive": 0}' > /dev/null
curl -s http://localhost:11434/api/generate -d '{"model": "nomic-embed-text", "keep_alive": 0}' > /dev/null
echo "✅ Modèles déchargés. La VRAM est libre pour lancer un jeu !"
