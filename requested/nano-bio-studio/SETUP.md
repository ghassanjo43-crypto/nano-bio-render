# 🚀 NanoBio Studio - Setup Guide

Complete installation and deployment instructions for Windows, macOS, and Linux.

---

## Table of Contents

1. [Local Installation](#local-installation)
2. [Cloud Deployment](#cloud-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Verification](#verification)
5. [Troubleshooting](#troubleshooting)

---

## Local Installation

### Prerequisites

- **Python 3.8 or higher** ([Download Python](https://www.python.org/downloads/))
- **pip** (included with Python)
- **Git** (optional, for cloning repository)

### Step-by-Step Installation

#### Windows

1. **Open Command Prompt or PowerShell**

   ```powershell
   # Navigate to the project directory
   cd d:\nano_bio-26_1
   ```

2. **Create virtual environment (recommended)**

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**

   ```powershell
   pip install -r requirements.txt
   ```

4. **Run the application**

   ```powershell
   streamlit run app.py
   ```

5. **Access in browser**

   The app automatically opens at `http://localhost:8501`

   If it doesn't open automatically, manually navigate to the URL.

#### macOS / Linux

1. **Open Terminal**

   ```bash
   # Navigate to the project directory
   cd ~/nano_bio-26_1
   ```

2. **Create virtual environment (recommended)**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**

   ```bash
   streamlit run app.py
   ```

5. **Access in browser**

   Open `http://localhost:8501` in your browser

---

## Cloud Deployment

### Option 1: Streamlit Community Cloud (Free)

**Best for**: Sharing with students, small groups, demonstrations

1. **Create GitHub repository**
   - Push your code to GitHub
   - Make sure all files are committed

2. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository and branch
   - Set main file path: `app.py`
   - Click "Deploy"

3. **Configuration** (optional)
   - Add secrets in Streamlit Cloud dashboard
   - Configure custom domain

4. **Access**
   - Your app will be available at: `https://[your-app-name].streamlit.app`

**Limitations**:
- Free tier: Limited resources
- Public apps only (unless upgraded)
- May sleep after inactivity

### Option 2: Heroku

**Best for**: Production deployments, more control

1. **Install Heroku CLI**
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku
   
   # Windows
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Create Heroku app**
   ```bash
   heroku login
   heroku create nanobio-studio
   ```

3. **Create Procfile**
   ```
   web: sh setup.sh && streamlit run app.py
   ```

4. **Create setup.sh**
   ```bash
   mkdir -p ~/.streamlit/
   echo "\
   [server]\n\
   headless = true\n\
   port = $PORT\n\
   enableCORS = false\n\
   \n\
   " > ~/.streamlit/config.toml
   ```

5. **Deploy**
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

### Option 3: AWS / Azure / Google Cloud

**Best for**: Enterprise deployments, high traffic

See detailed cloud provider guides in `/docs/cloud-deployment/`

---

## Docker Deployment

### Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### Build and Run

```bash
# Build Docker image
docker build -t nanobio-studio .

# Run container
docker run -p 8501:8501 nanobio-studio
```

### Docker Compose (with persistent storage)

```yaml
version: '3.8'

services:
  nanobio:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
    environment:
      - STREAMLIT_SERVER_PORT=8501
```

Run with:
```bash
docker-compose up
```

---

## Verification

### Test Installation

1. **Check Python version**
   ```bash
   python --version
   # Should show Python 3.8 or higher
   ```

2. **Verify dependencies**
   ```bash
   pip list
   # Should show streamlit, pandas, numpy, matplotlib
   ```

3. **Run application**
   ```bash
   streamlit run app.py
   ```

4. **Test functionality**
   - Navigate through all pages
   - Create a design
   - Run simulation
   - Export data

### Expected Output

When you run `streamlit run app.py`, you should see:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.x:8501
```

---

## Configuration

### Streamlit Configuration

Create `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
font = "sans serif"

[server]
port = 8501
enableCORS = false
enableXsrfProtection = true
maxUploadSize = 200

[browser]
gatherUsageStats = false
```

### Environment Variables

Create `.env` file (optional):

```env
STREAMLIT_SERVER_PORT=8501
STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
INSTRUCTOR_PASSWORD=your_secure_password
```

---

## Troubleshooting

### Issue: `streamlit: command not found`

**Solution**:
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Or install globally
pip install streamlit
```

### Issue: `ImportError: No module named 'pages.design'`

**Solution**:
```bash
# Check directory structure
ls pages/
# Should show: design.py, simulation.py, etc.

# If missing, verify you're in the correct directory
pwd  # Should show path to nano_bio-26_1
```

### Issue: Port 8501 already in use

**Solution**:
```bash
# Option 1: Use different port
streamlit run app.py --server.port 8502

# Option 2: Kill process on port 8501
# Windows
netstat -ano | findstr :8501
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:8501 | xargs kill -9
```

### Issue: `FileNotFoundError: data/nanoparticles.json`

**Solution**:
```bash
# Check data files exist
ls data/
# Should show: nanoparticles.json, targets.json

# If missing, verify complete installation
```

### Issue: Plots not displaying

**Solution**:
```bash
# Update matplotlib
pip install --upgrade matplotlib

# Clear Streamlit cache
streamlit cache clear
```

### Issue: Slow performance

**Solutions**:
- Close other browser tabs
- Reduce simulation time points in code
- Use smaller batch sizes
- Check system resources (RAM/CPU)

### Issue: Can't access from other devices on network

**Solution**:
```bash
# Run with network URL enabled
streamlit run app.py --server.address 0.0.0.0

# Then access from other devices using:
http://<your-ip-address>:8501
```

---

## Updating

### Update to Latest Version

```bash
# Pull latest changes (if using Git)
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Restart application
streamlit run app.py
```

---

## Uninstallation

### Remove Virtual Environment

```bash
# Deactivate
deactivate

# Remove directory
rm -rf venv  # macOS/Linux
rmdir /s venv  # Windows
```

### Complete Removal

```bash
# Remove entire project
rm -rf nano_bio-26_1  # macOS/Linux
rmdir /s nano_bio-26_1  # Windows
```

---

## Performance Optimization

### For Large Classes (>50 students)

1. **Use cloud deployment** with auto-scaling
2. **Enable caching** in Streamlit
3. **Pre-compute expensive operations**
4. **Use CDN** for static assets
5. **Implement user sessions** properly

### Code Optimization

In `app.py`, add:

```python
@st.cache_data
def load_nanoparticles():
    # Cache expensive data loading
    with open('data/nanoparticles.json', 'r') as f:
        return json.load(f)
```

---

## Security Best Practices

### For Production Deployment

1. **Change default instructor password**
   - Edit `pages/instructor.py`
   - Use strong password

2. **Enable HTTPS**
   - Use reverse proxy (nginx)
   - Configure SSL certificates

3. **Restrict access**
   - Use authentication if needed
   - IP whitelisting for instructor features

4. **Regular updates**
   - Keep dependencies updated
   - Monitor security advisories

---

## Support

### Getting Help

- **Documentation**: See README.md
- **Issues**: Report on GitHub Issues
- **Email**: info@expertsgroup.me
- **Community**: [Forum link]

### Reporting Bugs

Include:
1. Operating system and version
2. Python version
3. Error message (full traceback)
4. Steps to reproduce
5. Expected vs actual behavior

---

## Additional Resources

- **Streamlit Documentation**: https://docs.streamlit.io
- **Python Virtual Environments**: https://docs.python.org/3/tutorial/venv.html
- **Docker Documentation**: https://docs.docker.com
- **Heroku Documentation**: https://devcenter.heroku.com

---

**Last Updated**: January 2024  
**Version**: 1.0
