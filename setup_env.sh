#!/bin/bash

# Setup script for .env configuration
# Copies .env.example to .env if it doesn't exist

echo "================================"
echo "Environment Setup"
echo "================================"
echo ""

if [ -f ".env" ]; then
    echo "✓ .env file already exists"
    echo ""
    echo "To reconfigure, either:"
    echo "  1. Edit .env directly"
    echo "  2. Delete .env and run this script again"
else
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your credentials:"
    echo ""
    echo "  Required:"
    echo "    - AZURE_OPENAI_ENDPOINT"
    echo "    - AZURE_OPENAI_API_KEY"
    echo "    - AZURE_OPENAI_GPT4O_DEPLOYMENT"
    echo "    - DATABRICKS_HOST"
    echo "    - DATABRICKS_TOKEN"
    echo "    - GENIE_SPACE_ID"
    echo ""
    echo "  Optional (for enhanced features):"
    echo "    - RAG_ENABLED=true (for document-based Q&A)"
    echo "    - CACHE_ENABLED=true (for smart SQL caching)"
    echo ""
fi

echo "================================"
echo "Next Steps"
echo "================================"
echo ""
echo "1. Edit .env file:"
echo "   nano .env"
echo ""
echo "2. Install dependencies (if not done):"
echo "   pip install -r requirements.txt"
echo ""
echo "3. Run the system:"
echo "   python -m src.main_simple"
echo ""
echo "4. Or run tests:"
echo "   python test_smart_system_simple.py"
echo ""
