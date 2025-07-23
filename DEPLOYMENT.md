# Deployment Guide

This guide covers various deployment options for the NHA Healthcare Facilities Dashboard.

## 🚀 Quick Deploy Options

### 1. Streamlit Community Cloud (Recommended)

**Pros:** Free, easy setup, automatic deployments
**Cons:** Resource limits, public repositories only

**Steps:**
1. Upload your repository to GitHub (public)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select your repository
5. Set main file path: `dashboard.py`
6. Deploy!

**URL:** Your app will be available at `https://[your-username]-[repo-name]-[branch].streamlit.app`

### 2. Heroku Deployment

**Pros:** Reliable hosting, custom domains
**Cons:** Paid service, more complex setup

**Required Files:**
```bash
# Create Procfile
echo "web: streamlit run dashboard.py --server.port=\$PORT --server.address=0.0.0.0" > Procfile

# Create runtime.txt
echo "python-3.11.0" > runtime.txt
```

**Steps:**
1. Install Heroku CLI
2. `heroku create your-app-name`
3. `git push heroku main`

### 3. Docker Deployment

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Commands:**
```bash
# Build image
docker build -t nha-dashboard .

# Run container
docker run -p 8501:8501 nha-dashboard
```

### 4. Local Development

**Quick Start:**
```bash
# Clone repository
git clone https://github.com/your-username/nha-healthcare-dashboard.git
cd nha-healthcare-dashboard

# Setup environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
streamlit run dashboard.py
```

## 🔧 Configuration for Deployment

### Environment Variables

Create `.env` file for production:
```bash
# Data settings
DATA_PATH=/path/to/data/NHA_Master_merged_TEST.csv
MAX_ROWS=1000000

# Performance settings
ENABLE_AI_SEARCH=false
MAP_SAMPLE_SIZE=2000

# UI settings
PAGE_TITLE="NHA Healthcare Facilities Dashboard"
PAGE_ICON=🏥
```

### Streamlit Configuration

Create `.streamlit/config.toml`:
```toml
[server]
port = 8501
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
serverAddress = "0.0.0.0"

[theme]
primaryColor = "#FF6B6B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
```

## 📊 Production Optimizations

### Data Handling
```python
# In config/settings.py
PRODUCTION_CONFIG = {
    'max_data_rows': 500000,  # Limit for large datasets
    'enable_sampling': True,
    'sample_size': 10000,
    'cache_ttl': 3600,  # 1 hour cache
}
```

### Performance Settings
```python
# Enable caching for production
@st.cache_data(ttl=3600)
def load_data():
    # Data loading logic
    pass

@st.cache_resource
def initialize_search_engine():
    # Search engine initialization
    pass
```

## 🔒 Security Considerations

### Data Privacy
- Remove sensitive information from datasets
- Use environment variables for API keys
- Implement proper input validation

### Access Control
```python
# Simple password protection
def check_password():
    def password_entered():
        if st.session_state["password"] == "your_password":
            st.session_state["password_correct"] = True
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", 
                     on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", 
                     on_change=password_entered, key="password")
        st.error("Password incorrect")
        return False
    else:
        return True
```

## 🐛 Troubleshooting

### Common Issues

**Memory Issues:**
- Reduce `MAP_SAMPLE_SIZE` in config
- Enable data sampling
- Use `@st.cache_data` decorators

**Slow Loading:**
- Optimize data loading with chunking
- Implement lazy loading
- Use indexed data formats

**Deployment Failures:**
- Check requirements.txt compatibility
- Verify Python version
- Review log files

### Monitoring

**Health Check Endpoint:**
```python
# Add to main application
def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}
```

**Logging:**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log important events
logger.info("Application started")
logger.info(f"Data loaded: {len(data)} records")
```

## 📈 Scaling Considerations

### Database Integration
- Replace CSV with PostgreSQL/MongoDB
- Implement proper indexing
- Use connection pooling

### Caching Strategy
- Redis for session data
- CDN for static assets
- Database query caching

### Load Balancing
- Multiple Streamlit instances
- Nginx reverse proxy
- Container orchestration

## 🔄 CI/CD Pipeline

**GitHub Actions Example:**
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Deploy to Streamlit Cloud
      run: |
        # Deployment scripts
        echo "Deploying to production..."
```

## 📞 Support

For deployment issues:
1. Check the troubleshooting section
2. Review deployment logs
3. Test locally first
4. Check resource limits

---

**Choose the deployment method that best fits your needs and resources!** 🚀
