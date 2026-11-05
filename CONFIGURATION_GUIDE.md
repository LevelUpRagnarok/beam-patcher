# Beam Patcher - Configuration Guide

## Quick Start

### 1. Copy Configuration File
```bash
# Copy example configuration
cp config.production.example.yml config.yml
```

### 2. Edit Configuration
Open `config.yml` and update these **required** settings:

```yaml
app:
  name: "Your Server Name"
  server_name: "Your Server Name"
  client_exe: "YourGame.exe"

patcher:
  mirrors:
    - name: "Main Server"
      url: "https://patch.yourserver.com"
      priority: 1
  
  patch_list_url: "https://patch.yourserver.com/patchlist.txt"
```

### 3. Test Configuration
```bash
# Run patcher in debug mode
./beam-patcher.exe
```

---

## Configuration Sections

### **APP Settings**

#### Basic Information
```yaml
app:
  name: "MyRO Server"           # Server name shown in UI
  version: "1.0.0"              # Config version for tracking
  window_title: "MyRO Patcher"  # Window title bar text
  client_exe: "Ragnarok.exe"    # Game executable name
  setup_exe: "setup.exe"        # Setup tool executable
  server_name: "MyRO"           # Short server name
```

#### Optional Features
```yaml
  # Background Music
  bgm_autoplay: true
  bgm_file: "assets/bgm.mp3"    # Path to MP3/OGG/WAV file
  
  # Video Background (Resource intensive!)
  video_background_enabled: false
  video_background_file: "assets/trailer.mp4"
  
  # Screenshot Grid/Slideshow
  grid_images:
    - "assets/screenshot1.png"
    - "assets/screenshot2.png"
    - "assets/screenshot3.png"
  
  # Social Links
  discord_url: "https://discord.gg/yourcode"
  register_url: "https://yourserver.com/register"
```

---

### **PATCHER Settings**

#### Mirror Servers
```yaml
patcher:
  mirrors:
    # Primary server (priority 1 = tried first)
    - name: "USA Mirror"
      url: "https://patch-usa.yourserver.com"
      priority: 1
    
    # Fallback servers (priority 2+)
    - name: "EU Mirror"
      url: "https://patch-eu.yourserver.com"
      priority: 2
    
    - name: "Asia Mirror"
      url: "https://patch-asia.yourserver.com"
      priority: 3
```

**Tips:**
- Use CDN for better performance
- Add multiple mirrors for redundancy
- Test all mirror URLs before deploying

#### Patch List
```yaml
  patch_list_url: "https://patch.yourserver.com/patchlist.txt"
  target_grf: "data.grf"
  allow_manual_patch: true
  verify_checksums: true
```

**patchlist.txt format:**
```
001_initial.beam
002_update.beam
003_hotfix.beam
```

---

### **UI Settings**

#### Window Layout
```yaml
ui:
  layout:
    width: 800    # Window width in pixels
    height: 600   # Window height in pixels
```

**Common resolutions:**
- `800x600` - Small (good for 1366x768 screens)
- `1000x650` - Medium (good for 1920x1080 screens)
- `1200x700` - Large (good for 2K/4K screens)

#### Custom Styling
```yaml
  theme: "default"
  custom_css: "themes/custom.css"  # Optional CSS file
  logo: "assets/logo.png"          # Custom logo
  background: "assets/bg.jpg"      # Custom background
```

#### News & Status
```yaml
  news_feed_url: "https://yourserver.com/api/news"
  server_status_url: "https://yourserver.com/api/status"
  status_image_url: "assets/server-online.png"
```

**News API format (JSON):**
```json
[
  {
    "title": "Server Maintenance",
    "content": "Maintenance scheduled for...",
    "date": "2026-01-18"
  }
]
```

---

### **SSO (Single Sign-On)**

```yaml
sso:
  enabled: true
  login_url: "https://auth.yourserver.com/oauth/authorize"
  token_url: "https://auth.yourserver.com/oauth/token"
  client_id: "beam-patcher"
  redirect_uri: "http://localhost:8080/callback"
```

**Requirements:**
- OAuth2 server configured
- Client ID registered
- Redirect URI whitelisted

---

### **Auto-Updater**

```yaml
updater:
  enabled: true
  check_url: "https://patch.yourserver.com/version.json"
  update_url: "https://patch.yourserver.com/updates"
  auto_update: false
```

**version.json format:**
```json
{
  "version": "1.0.1",
  "required": false,
  "download_url": "https://patch.yourserver.com/BeamPatcher-1.0.1.exe",
  "changelog": "- Bug fixes\n- Performance improvements",
  "sha256": "abc123..."
}
```

---

## Patch Formats Supported

### 1. BEAM Format (.beam)
**Best for:** New servers, best performance

```
Advantages:
✅ Zlib compression (BEAM v1; not encrypted)
✅ Built-in MD5 verification
✅ Smallest file size
✅ Modern format

Disadvantages:
❌ Not compatible with GRF Editor
❌ Only works with Beam Patcher
```

### 2. THOR Format (.thor)
**Best for:** Compatibility with existing tools

```
Advantages:
✅ Compatible with GRF Editor
✅ Compatible with Thor Patcher
✅ Standard RO format
✅ Community tool support

Disadvantages:
❌ Slower compression (Zlib)
❌ Larger file size
```

### 3. RGZ Format (.rgz)
**Best for:** Alternative to THOR

```
Advantages:
✅ Compatible with GRF Editor
✅ Gzip compression

Disadvantages:
❌ Less common format
❌ Limited tool support
```

### 4. GRF Format (.grf)
**Best for:** Full game data replacement

```
Use cases:
- Complete game reinstall
- Major version updates
- Full data replacement
```

---

## Server Setup

### 1. Directory Structure
```
patch-server/
├── patchlist.txt          # List of patches
├── version.json           # Patcher version info
├── patches/
│   ├── 001_initial.beam
│   ├── 002_update.beam
│   └── 003_hotfix.beam
└── patcher/
    └── BeamPatcher-1.0.1.exe
```

### 2. Web Server Configuration

#### Apache (.htaccess)
```apache
# Enable CORS
Header set Access-Control-Allow-Origin "*"

# Cache control
<FilesMatch "\.(beam|thor|rgz|grf)$">
    Header set Cache-Control "max-age=31536000, public"
</FilesMatch>

# Enable compression
AddOutputFilterByType DEFLATE text/plain
AddOutputFilterByType DEFLATE text/xml
```

#### Nginx
```nginx
location /patches/ {
    add_header Access-Control-Allow-Origin *;
    add_header Cache-Control "public, max-age=31536000";
    
    # Enable range requests for large files
    add_header Accept-Ranges bytes;
}
```

### 3. CDN Setup (Recommended)

**Cloudflare:**
```
1. Add domain to Cloudflare
2. Enable caching for patch files
3. Set cache TTL to 1 month
4. Enable "Always Online"
```

**AWS CloudFront:**
```
1. Create S3 bucket for patches
2. Configure CloudFront distribution
3. Set cache behavior for *.beam, *.thor files
4. Enable HTTPS
```

---

## Creating Patches

### Using Beam Tools UI

#### 1. Single File Patch
```
Input Path: D:\update\newfile.txt
Base Path: D:\update
Output Path: D:\patches\001_update.beam
Format: BEAM

Result: root/newfile.txt
```

#### 2. Directory Patch
```
Input Path: D:\update\data\
Base Path: D:\update
Output Path: D:\patches\002_content.beam
Format: BEAM

Result: 
root/data/texture/...
root/data/model/...
root/data/sprite/...
```

#### 3. THOR Format (GRF Editor Compatible)
```
Input Path: D:\update\data\
Base Path: D:\update
Output Path: D:\patches\003_update.thor
Format: THOR

Result in GRF Editor:
└── root/
    └── data/
        ├── texture/
        ├── model/
        └── sprite/
```

---

## Deployment Checklist

### Before Deployment
- [ ] Test all mirror URLs
- [ ] Verify patchlist.txt is accessible
- [ ] Test patch downloads
- [ ] Verify checksums
- [ ] Test on clean install
- [ ] Check all links (Discord, Register, etc.)
- [ ] Test on different screen resolutions
- [ ] Verify BGM/video files load correctly

### After Deployment
- [ ] Monitor download speeds
- [ ] Check server logs for errors
- [ ] Monitor bandwidth usage
- [ ] Test auto-updater
- [ ] Collect user feedback
- [ ] Monitor error reports

---

## Troubleshooting

### Patcher won't start
```
1. Check config.yml syntax (YAML validation)
2. Verify all file paths exist
3. Check permissions
4. Run from command line to see errors
```

### Patches won't download
```
1. Verify mirror URLs are accessible
2. Check patchlist.txt format
3. Verify CORS headers on server
4. Check firewall settings
5. Test with different mirror
```

### "Cannot convert to GRF container" error
```
This was fixed in latest version!
- THOR files now use proper Zlib compression
- Files have correct root/ prefix
- Update to latest beam-tools-ui
```

### Performance issues
```
1. Disable video background
2. Reduce window size
3. Optimize images (compress JPG/PNG)
4. Use CDN for patch files
5. Enable caching on server
```

---

## Best Practices

### 1. Patch Naming
```
Good:
✅ 001_initial_release.beam
✅ 002_new_maps_update.beam
✅ 003_christmas_event.beam

Bad:
❌ patch.beam
❌ update.beam
❌ test123.beam
```

### 2. Patch Size
```
Recommended: < 100MB per patch
Maximum: < 500MB per patch

For large updates:
- Split into multiple patches
- Use full GRF replacement
- Consider torrent distribution
```

### 3. Version Control
```
Keep track of:
- Config version in config.yml
- Patch numbers in patchlist.txt
- Patcher version in version.json

Use semantic versioning:
- Major.Minor.Patch (1.0.0)
- Increment for each update
```

### 4. Backup Strategy
```
Always backup:
- config.yml
- patchlist.txt
- All patch files
- version.json

Recommended: Daily backups
```

---

## Support & Resources

### Official Repository
- GitHub: https://github.com/beamguides/beam-patcher

### Documentation
- Full documentation: See README.md
- API documentation: See API.md
- Format specifications: See FORMATS.md

### Community
- Discord: https://discord.gg/DeMpCu2Q

---

## License
This project is dual-licensed under MIT and Apache 2.0 licenses.
See LICENSE-MIT and LICENSE-APACHE for details.
