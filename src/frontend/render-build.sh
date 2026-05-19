#!/bin/bash

# Exit on error
set -e

echo "Installing dependencies..."
npm ci --legacy-peer-deps

echo "Building frontend..."
npm run build

echo "Build complete!"
