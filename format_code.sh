#!/bin/bash

# Code formatting script for the Course Materials Assistant project
# This script automatically formats Python backend and frontend code

set -e  # Exit on any error

echo "🎨 Formatting Code..."
echo "===================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

# Python Backend Formatting
echo ""
print_status "Formatting Python backend code..."

# Run isort to sort imports
print_status "Sorting Python imports with isort..."
uv run isort backend/ main.py
print_success "Python imports sorted"

# Run Black to format code
print_status "Formatting Python code with Black..."
uv run black backend/ main.py
print_success "Python code formatted"

# Frontend Formatting
echo ""
print_status "Formatting frontend code..."

cd frontend

# Check if npm is available
if ! command -v npm > /dev/null 2>&1; then
    print_error "npm not found. Please install Node.js and npm to format frontend code."
    cd ..
    exit 1
fi

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    print_status "Installing frontend dependencies..."
    npm install
fi

# Run Prettier and ESLint fix
print_status "Formatting frontend code with Prettier and ESLint..."
npm run quality:fix
print_success "Frontend code formatted"

cd ..

echo ""
echo "===================="
print_success "All code has been formatted!"
echo ""
print_status "Run './quality_check.sh' to verify formatting is correct."