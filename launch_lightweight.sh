#!/bin/bash

# Lightweight NHA Dashboard Launcher
# Automatically installs dependencies if missing

echo "🏥 Starting NHA Healthcare Facilities Dashboard..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    # Try to activate the local venv
    if [ -d "$SCRIPT_DIR/venv" ]; then
        echo "🔄 Activating local virtual environment..."
        source "$SCRIPT_DIR/venv/bin/activate"
    else
        echo "⚠️  No virtual environment found. Using system Python."
    fi
fi

# Check for required files
if [ ! -f "$SCRIPT_DIR/dashboard.py" ]; then
    echo "❌ Dashboard file 'dashboard.py' not found"
    exit 1
fi

# Check if streamlit is available
if ! command -v streamlit &> /dev/null; then
    echo "📦 Installing streamlit..."
    pip install streamlit pandas plotly folium streamlit-folium
fi

# Check for data file
DATA_FOUND=false
for data_file in "data/NHA_Master_merged_TEST.csv" "NHA_Master_merged_TEST.csv" "../NHA_Master_merged_TEST.csv"; do
    if [ -f "$SCRIPT_DIR/$data_file" ]; then
        DATA_FOUND=true
        echo "✅ Data file found: $data_file"
        break
    fi
done

if [ "$DATA_FOUND" = false ]; then
    echo "⚠️  Warning: NHA_Master_merged_TEST.csv not found"
    echo "   Please ensure the data file is in the correct location"
fi

# Change to script directory
cd "$SCRIPT_DIR"

echo "🚀 Launching dashboard..."
echo ""
echo "📍 Dashboard will be available at:"
echo "   • Local: http://localhost:8501"
echo ""
echo "💡 Press Ctrl+C to stop the dashboard"
echo "🔧 Using lightweight search (no AI models for stability)"
echo ""

# Run the dashboard with error handling
streamlit run dashboard.py --server.port 8501 --server.headless true

# If streamlit fails, provide helpful information
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Dashboard failed to start"
    echo "💡 Troubleshooting tips:"
    echo "   1. Check if port 8501 is already in use"
    echo "   2. Ensure all dependencies are installed: pip install -r requirements.txt"
    echo "   3. Verify data file exists: ls -la data/NHA_Master_merged_TEST.csv"
fi
