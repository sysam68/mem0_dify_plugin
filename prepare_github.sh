#!/bin/bash

# Mem0 Dify Plugin - GitHub Preparation Script
# This script helps you prepare the plugin for upload to GitHub

set -e

echo "🚀 Preparing Mem0 Dify Plugin for upload to GitHub..."
echo ""

# 1. Replace README
if [ -f "README_NEW.md" ]; then
    echo "📝 Updating README.md..."
    mv README.md README_OLD.md
    mv README_NEW.md README.md
    echo "   ✅ README.md updated"
else
    echo "   ℹ️  README_NEW.md not found, skipping"
fi

# 2. Create LICENSE
if [ ! -f "LICENSE" ]; then
    echo "📄 Creating LICENSE file..."
    cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2025 yevanchen
Extensively Refactored and Significantly Enhanced by: beersoccer
Copyright (c) 2025 beersoccer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF
    echo "   ✅ LICENSE created"
else
    echo "   ℹ️  LICENSE already exists, skipping"
fi

# 3. Initialize Git (if needed)
if [ ! -d ".git" ]; then
    echo "📦 Initializing Git repository..."
    git init
    echo "   ✅ Git repository initialized"
else
    echo "   ℹ️  Git repository already exists"
fi

# 4. Add all files
echo "📂 Adding files to Git..."
git add .
echo "   ✅ Files added"

# 5. Create commit
echo "💾 Creating Git commit..."
git commit -m "feat: Mem0 Dify Plugin v0.0.8

- 8 complete memory management tools
- Full Mem0 API v2 support
- Advanced filters (AND/OR logic)
- Multi-entity support (user/agent/app/run)
- Metadata system
- 4 language support (en/zh/pt/ja)
- 100% backward compatible" || echo "   ℹ️  No new changes to commit"

echo ""
echo "✅ Preparation complete!"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Create a new repository on GitHub:"
echo "   Visit: https://github.com/new"
echo "   Name: dify-plugin-mem0"
echo "   ❌ Do NOT add README, .gitignore, or LICENSE"
echo ""
echo "2. Add remote repository and push (replace yourusername):"
echo "   git remote add origin https://github.com/yourusername/dify-plugin-mem0.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "3. Install in Dify:"
echo "   Settings → Plugins → Install from GitHub"
echo "   Enter: yourusername/dify-plugin-mem0"
echo ""
echo "🎉 Done!"
