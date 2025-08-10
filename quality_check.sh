#!/bin/bash

# Quality check script for the Course Materials Assistant project
# This script runs all code quality checks for both Python backend and frontend

set -e  # Exit on any error

echo "🔍 Running Code Quality Checks..."
echo "================================="

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    print_error "pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

# Python Backend Quality Checks
echo ""
print_status "Checking Python backend code quality..."

# Check if Black is available
if ! uv run black --version > /dev/null 2>&1; then
    print_error "Black not found. Please install dependencies with 'uv sync'"
    exit 1
fi

# Run Black check
print_status "Running Black formatter check..."
if uv run black --check backend/ main.py; then
    print_success "Python code formatting is correct"
else
    print_warning "Python code needs formatting. Run 'uv run black backend/ main.py' to fix"
fi

# Run isort check
print_status "Running isort import sorting check..."
if uv run isort --check-only backend/ main.py; then
    print_success "Python imports are correctly sorted"
else
    print_warning "Python imports need sorting. Run 'uv run isort backend/ main.py' to fix"
fi

# Run flake8 linting
print_status "Running flake8 linting..."
if uv run flake8 backend/ main.py; then
    print_success "Python linting passed"
else
    print_warning "Python linting issues found"
fi

# Frontend Quality Checks
echo ""
print_status "Checking frontend code quality..."

cd frontend

# Check if npm is available
if ! command -v npm > /dev/null 2>&1; then
    print_warning "npm not found. Skipping frontend quality checks."
    print_warning "Install Node.js and npm to enable frontend quality checks."
else
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..."
        npm install
    fi

    # Run ESLint check
    print_status "Running ESLint check..."
    if npm run lint; then
        print_success "Frontend linting passed"
    else
        print_warning "Frontend linting issues found. Run 'npm run lint:fix' to fix"
    fi

    # Run Prettier check
    print_status "Running Prettier formatting check..."
    if npm run format:check; then
        print_success "Frontend formatting is correct"
    else
        print_warning "Frontend code needs formatting. Run 'npm run format' to fix"
    fi
fi

cd ..

echo ""
echo "================================="
print_success "Quality check completed!"
echo ""
print_status "To fix formatting issues:"
echo "  Backend:  ./format_code.sh"
echo "  Frontend: cd frontend && npm run quality:fix"