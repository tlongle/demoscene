#!/usr/bin/env bash
# ==============================================================================
# DEMOSCENE - Asset Pack Bundler & Extractor Helper
# ==============================================================================
set -e

ACTION="${1:-pack}"
ARCHIVE_NAME="demoscene_assets.tar.gz"

if [ "$ACTION" = "pack" ]; then
    echo "📦 Packing data/assets/ into $ARCHIVE_NAME..."
    if [ ! -d "data/assets" ]; then
        echo "❌ data/assets directory not found."
        exit 1
    fi
    tar -czf "$ARCHIVE_NAME" data/assets/
    echo "✓ Created $ARCHIVE_NAME ($(du -h "$ARCHIVE_NAME" | cut -f1))"
    echo "  You can copy this archive to any machine and run: ./scripts/bundle_assets.sh unpack"

elif [ "$ACTION" = "unpack" ]; then
    if [ ! -f "$ARCHIVE_NAME" ]; then
        echo "❌ $ARCHIVE_NAME not found in current directory."
        exit 1
    fi
    echo "📂 Unpacking $ARCHIVE_NAME into data/assets/..."
    tar -xzf "$ARCHIVE_NAME"
    echo "✓ Assets unpacked successfully into data/assets/"
else
    echo "Usage: ./scripts/bundle_assets.sh [pack|unpack]"
    exit 1
fi
