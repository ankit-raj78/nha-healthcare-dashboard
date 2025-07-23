#!/bin/bash

# GitHub Upload Setup Script for NHA Healthcare Facilities Dashboard
# This script helps prepare and upload the project to GitHub

echo "🚀 GitHub Upload Setup for NHA Healthcare Dashboard"
echo "=================================================="

# Check if git is configured
echo "📋 Checking Git configuration..."
if ! git config user.name >/dev/null; then
    echo "⚠️  Git user.name not set. Please configure it:"
    echo "   git config --global user.name \"Your Name\""
    exit 1
fi

if ! git config user.email >/dev/null; then
    echo "⚠️  Git user.email not set. Please configure it:"
    echo "   git config --global user.email \"your.email@example.com\""
    exit 1
fi

echo "✅ Git is configured"
echo "   User: $(git config user.name)"
echo "   Email: $(git config user.email)"

# Check current status
echo ""
echo "📊 Current repository status:"
git log --oneline -5 2>/dev/null || echo "   (No commits yet)"

echo ""
echo "📁 Repository contents:"
git ls-files | head -10
if [ $(git ls-files | wc -l) -gt 10 ]; then
    echo "   ... and $(expr $(git ls-files | wc -l) - 10) more files"
fi

echo ""
echo "🌐 Next steps to upload to GitHub:"
echo ""
echo "1️⃣  Create a new repository on GitHub:"
echo "   - Go to https://github.com/new"
echo "   - Repository name: nha-healthcare-dashboard (or your preferred name)"
echo "   - Description: Interactive Streamlit dashboard for NHA healthcare facilities data analysis"
echo "   - Choose Public or Private"
echo "   - Do NOT initialize with README, .gitignore, or license (we already have them)"
echo ""
echo "2️⃣  Add GitHub as remote origin:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/REPOSITORY_NAME.git"
echo ""
echo "3️⃣  Push to GitHub:"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4️⃣  Optional: Set up GitHub Pages (if you want to host documentation):"
echo "   - Go to repository Settings > Pages"
echo "   - Select source: Deploy from branch"
echo "   - Branch: main, folder: / (root)"
echo ""

echo "💡 Helpful commands:"
echo "   git remote -v                    # Check remote repositories"
echo "   git status                       # Check repository status"
echo "   git log --oneline               # View commit history"
echo "   git push origin main            # Push changes to GitHub"
echo ""

echo "📝 Repository features included:"
echo "   ✅ Professional README.md with installation and usage instructions"
echo "   ✅ MIT License"
echo "   ✅ Contributing guidelines (CONTRIBUTING.md)"
echo "   ✅ GitHub Actions CI/CD pipeline"
echo "   ✅ Issue templates for bugs and feature requests"
echo "   ✅ Proper .gitignore for Python projects"
echo "   ✅ Basic test structure with pytest"
echo "   ✅ Modular code architecture"
echo "   ✅ Comprehensive documentation"
echo ""

echo "🔒 Security notes:"
echo "   - Virtual environment (venv/) is gitignored"
echo "   - Sensitive files are excluded via .gitignore"
echo "   - Data files are included (review if they contain sensitive information)"
echo ""

echo "🎯 Repository is ready for GitHub upload!"
echo "   Commit hash: $(git rev-parse --short HEAD)"
echo "   Files: $(git ls-files | wc -l) tracked files"
echo "   Size: $(du -sh . | cut -f1) total size"
