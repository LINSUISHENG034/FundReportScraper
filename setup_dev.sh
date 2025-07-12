#!/bin/bash

# Development setup script
# Run this script to set up the development environment

set -e  # Exit on any error

echo "🚀 Setting up Fund Report Scraper development environment..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install Poetry first:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
poetry install

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please review and update .env file with your configuration"
fi

# Start development services
echo "🐳 Starting development services (PostgreSQL, Redis, MinIO)..."
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose -f docker-compose.dev.yml ps | grep -q "Up"; then
    echo "✅ Development services are running"
else
    echo "❌ Some services failed to start. Check docker-compose logs:"
    docker-compose -f docker-compose.dev.yml logs
    exit 1
fi

echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Review and update the .env file"
echo "2. Run 'poetry shell' to activate the virtual environment"
echo "3. Run 'pytest' to ensure tests pass"
echo "4. Start development with 'uvicorn src.main:app --reload'"
echo ""
echo "Useful commands:"
echo "- poetry run pytest                    # Run tests"
echo "- poetry run black src tests          # Format code"
echo "- poetry run flake8 src tests         # Lint code"
echo "- docker-compose -f docker-compose.dev.yml logs  # View service logs"
echo "- docker-compose -f docker-compose.dev.yml down  # Stop services"