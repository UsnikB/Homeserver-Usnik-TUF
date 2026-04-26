# usnik-tuf Homelab

> From-scratch setup guide and config backup for a self-hosted media + automation homelab running on Windows 11 + WSL2 (Arch Linux) with Docker.

**Dashboard:** `https://usnik-tuf` (LAN) · `https://usnik-tuf-arch.tail25be85.ts.net` (Tailscale)

---

## Table of Contents

- [Hardware](#hardware)
- [Storage Layout](#storage-layout)
- [Host OS Setup](#host-os-setup)
- [WSL2 — Arch Linux Setup](#wsl2--arch-linux-setup)
- [Network Setup](#network-setup)
- [SSL — Custom Certificate Authority](#ssl--custom-certificate-authority)
- [Docker Infrastructure](#docker-infrastructure)
- [Service Deployment](#service-deployment)
  - [Gluetun (VPN Gateway)](#gluetun-vpn-gateway)
  - [qBittorrent](#qbittorrent)
  - [Prowlarr](#prowlarr)
  - [Radarr · Sonarr · Lidarr](#radarr--sonarr--lidarr)
  - [Bazarr](#bazarr)
  - [Jellyfin](#jellyfin)
  - [Jellyseerr](#jellyseerr)
  - [Portainer](#portainer)
  - [Cloudflared](#cloudflared)
  - [Glances (System Stats)](#glances-system-stats)
  - [Diskstats (Custom GPU + Disk API)](#diskstats-custom-gpu--disk-api)
  - [Uptime Kuma](#uptime-kuma)
  - [Homepage — Nginx Reverse Proxy](#homepage--nginx-reverse-proxy)
  - [Obsidian Remote](#obsidian-remote)
- [Nginx Configuration Reference](#nginx-configuration-reference)
- [Service Access Table](#service-access-table)
- [Post-Install Configuration](#post-install-configuration)
- [Maintenance & Backup](#maintenance--backup)

---

## Hardware

| Component | Spec |
|-----------|------|
| **Machine** | ASUS TUF Gaming laptop |
| **CPU** | AMD Ryzen 7 4800H — 8 cores / 16 threads |
| **GPU** | NVIDIA GeForce GTX 1660 Ti — Jellyfin NVENC transcoding |
| **RAM** | 8 GB (7.47 GiB usable) + 2 GiB swap |
| **SSD** | ~500 GB — mounted at `/mnt/e` in WSL2 |
| **HDD** | ~2 TB — mounted at `/mnt/d` in WSL2 |

---

## Storage Layout

| Mount | Disk | Role |
|-------|------|------|
| `/mnt/e` | SSD | Working dir: Docker `appdata/`, `compose/` files, active downloads |
| `/mnt/d` | HDD | Media library: Movies, TV Shows, Music |

**Key paths inside WSL2:**

```
/mnt/e/
├── compose/          # All docker-compose files (this repo)
├── appdata/          # Service persistent config & data
│   ├── homepage/     # Nginx config + dashboard HTML
│   ├── diskstats/    # Custom stats API script
│   ├── jellyfin/
│   ├── jellyseerr/
│   ├── radarr/ sonarr/ lidarr/ bazarr/ prowlarr/
│   ├── qbittorrent/
│   ├── gluetun/
│   └── portainer/
├── downloads/        # Active download staging (SSD for speed)
├── scripts/          # Utility scripts
└── project_plan/     # project-tracker container source

/mnt/d/media/
├── movies/
├── tv/
├── music/
└── adult/
```

---

## Host OS Setup

### Windows 11

1. Enable WSL2: run `wsl --install` in PowerShell (Admin)
2. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) — enable WSL2 backend
3. Install [Tailscale](https://tailscale.com/download) for Windows
4. Set up the WSL static IP script as a startup task (see [Network Setup](#network-setup))

**Docker Desktop settings:**
- Settings → General → "Use the WSL 2 based engine": ON
- Settings → Resources → WSL Integration: enable for your Arch distro

> **NVIDIA GPU in Docker**
> For Jellyfin NVENC support the GTX 1660 Ti driver must be installed on Windows. Docker Desktop passes GPU access through to containers via NVIDIA Container Toolkit — no extra WSL setup needed.

---

## WSL2 — Arch Linux Setup

```bash
# Install Arch WSL from Microsoft Store, then on first boot:
useradd -m -G wheel usnik
passwd usnik

# Install base packages
pacman -Syu
pacman -S base-devel git curl wget openssl python3 github-cli

# Set default user
echo -e "[user]\ndefault=usnik" >> /etc/wsl.conf
```

---

## Network Setup

### The Problem

WSL2 gets a new dynamic IP on every Windows restart. Services like Glances and Diskstats are reached from Docker containers via the host gateway IP, so a static alias is needed.

### Static IP Script

**File:** `scripts/wsl-static-ip.ps1`

```powershell
wsl -u root ip addr add 172.31.70.215/20 broadcast 172.31.79.255 dev eth0 label eth0:1 2>$null
```

**Register as a startup task:**
1. Open Task Scheduler → Create Task
2. Trigger: "At log on"
3. Action: `powershell.exe -File "C:\path\to\wsl-static-ip.ps1"`
4. Run with highest privileges

> The Docker host gateway from containers is `172.17.0.1` (docker0 bridge). Nginx reaches Glances (:61208) and Diskstats (:61209) at this IP.

### Client DNS / Hosts file

On any machine that needs to reach `https://usnik-tuf` over LAN, add:

```
192.168.0.6   usnik-tuf usnik-tuf-arch
```

Replace `192.168.0.6` with the machine's actual LAN IP.

### Tailscale

Install Tailscale on Windows. The machine is reachable at `usnik-tuf-arch.tail25be85.ts.net`. The Nginx SSL cert covers this FQDN.

---

## SSL — Custom Certificate Authority

All HTTPS traffic uses a self-signed CA. The CA cert must be trusted on each client machine.

All SSL files live in: `appdata/homepage/ssl/`

### Step 1 — Create the CA

```bash
cd /mnt/e/appdata/homepage/ssl

openssl genrsa -out MyLocalCA.key 4096
openssl req -x509 -new -nodes -key MyLocalCA.key -sha256 -days 3650 \
  -out MyLocalCA.crt \
  -subj "/C=IN/ST=WB/L=Kolkata/O=UsnikHomelab/CN=MyLocalCA"
cp MyLocalCA.crt MyLocalCA.pem
```

### Step 2 — Create the extension config

**File:** `appdata/homepage/ssl/ext.cnf` (already in this repo)

```ini
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = usnik-tuf-arch.tail25be85.ts.net
DNS.2 = usnik-tuf
DNS.3 = usnik-tuf-arch
DNS.4 = localhost
IP.1  = 127.0.0.1
```

> To add a new hostname, update `ext.cnf` and re-run Step 3. The CA does not need to be regenerated.

### Step 3 — Create the server certificate

```bash
cd /mnt/e/appdata/homepage/ssl

openssl genrsa -out master.key 2048
openssl req -new -key master.key -out master.csr \
  -subj "/C=IN/O=UsnikHomelab/CN=usnik-tuf"

openssl x509 -req -in master.csr -CA MyLocalCA.crt -CAkey MyLocalCA.key \
  -CAcreateserial -out master.crt -days 3650 -sha256 -extfile ext.cnf
```

### Step 4 — Trust the CA on Windows

```powershell
# Run in PowerShell (Admin)
Import-Certificate `
  -FilePath "\\wsl.localhost\Arch\mnt\e\appdata\homepage\ssl\MyLocalCA.crt" `
  -CertStoreLocation Cert:\LocalMachine\Root
```

Or: double-click `MyLocalCA.crt` → Install Certificate → Local Machine → Trusted Root Certification Authorities.

---

## Docker Infrastructure

### Networks

| Network | Purpose |
|---------|---------|
| `arr-network` | Media stack — Jellyfin, Arrs, qBit, Gluetun, Portainer |
| `homepage_homepage-net` | Dashboard stack — Nginx, Obsidian, Uptime Kuma |

Nginx (`homepage` container) is attached to **both** networks so it can reach all services.

```bash
# arr-network is created automatically by the arr compose stack.
# If recreating from scratch:
docker network create arr-network
```

### Deploy any stack

```bash
cd /mnt/e/compose/<service>
docker compose up -d
```

---

## Service Deployment

All compose files are in `compose/<service>/docker-compose.yml`. The full arr stack (Gluetun, qBittorrent, Prowlarr, all Arrs, Jellyfin, Jellyseerr, Stash) lives in a single file: `compose/arr/docker-compose.yml`.

---

### Gluetun (VPN Gateway)

Routes all traffic from qBittorrent, Prowlarr, and Stash through PIA VPN (Netherlands, OpenVPN).

Credentials are stored in `compose/arr/.env` (not committed — see `.env.example`):

```bash
# compose/arr/.env
PIA_USER=your_pia_username
PIA_PASSWORD=your_pia_password
```

```yaml
gluetun:
  image: qmcgaw/gluetun:latest
  container_name: gluetun
  cap_add:
    - NET_ADMIN
  devices:
    - /dev/net/tun:/dev/net/tun
  environment:
    - VPN_SERVICE_PROVIDER=private internet access
    - VPN_TYPE=openvpn
    - OPENVPN_USER=${PIA_USER}
    - OPENVPN_PASSWORD=${PIA_PASSWORD}
    - SERVER_REGIONS=Netherlands
    - TZ=Asia/Kolkata
    - FIREWALL_INPUT_PORTS=8090,9696,9999
  ports:
    - 8090:8090   # qBittorrent WebUI
    - 9696:9696   # Prowlarr
    - 9999:9999   # Stash
    - 6881:6881   # Torrent peers
  networks:
    - arr-network
```

---

### qBittorrent

Torrent client. All traffic exits through Gluetun VPN.

- **Access:** `https://usnik-tuf/qbittorrent/`
- Default credentials: `admin` / `adminadmin` — change on first login
- Post-install: Settings → WebUI → add `usnik-tuf` to allowed hostnames

---

### Prowlarr

Indexer manager. Syncs indexers to all Arrs automatically.

- **Access:** `https://usnik-tuf/prowlarr/`
- Post-install: Settings → General → URL Base: `/prowlarr`

---

### Radarr · Sonarr · Lidarr

Automated movie / TV / music downloading via Prowlarr + qBittorrent.

| Service | Access | URL Base setting |
|---------|--------|-----------------|
| Radarr | `https://usnik-tuf/radarr/` | `/radarr` |
| Sonarr | `https://usnik-tuf/sonarr/` | `/sonarr` |
| Lidarr | `https://usnik-tuf/lidarr/` | `/lidarr` |

All use the **Keep Prefix** proxy pattern — the URL Base must be set in each app under Settings → General.

---

### Bazarr

Automatic subtitle downloading.

- **Access:** `https://usnik-tuf/bazarr/`
- Post-install: Settings → General → Base URL: `/bazarr`
  (also stored in `appdata/bazarr/config/config.yaml` at `general.base_url`)

---

### Jellyfin

Media server with NVENC hardware transcoding.

- **Access:** `https://usnik-tuf/jellyfin/`

> **Required config after first run:**
> Set `<BaseUrl>/jellyfin</BaseUrl>` in `appdata/jellyfin/config/config/network.xml`, then restart the container. Without this, the reverse proxy subpath will not work.

Post-install: Dashboard → Playback → Transcoding → Hardware acceleration: `NVENC`. Enable H.264, HEVC, AV1.

---

### Jellyseerr

Media request portal — users browse and request movies/shows which go to Radarr/Sonarr.

- **Access:** `http://usnik-tuf:5055/` (direct port — see note below)

> **No subpath support:** Jellyseerr's Docker image is compiled with Next.js `basePath: "/"` hardcoded. It cannot be served at `/jellyseerr/` via a reverse proxy subpath — the auth middleware redirects to `/login` without any base prefix, which breaks the proxy chain. The homepage card redirects directly to port 5055.
>
> To fix this upstream: build a custom image with `basePath: '/jellyseerr'` in `next.config.js`.

Post-install: connect to Jellyfin at `http://jellyfin:8096` (internal Docker hostname). Connect Radarr at `http://radarr:7878` and Sonarr at `http://sonarr:8989`.

---

### Portainer

Docker management UI.

- **Access:** `https://usnik-tuf/portainer/`
- **File:** `compose/portainer/docker-compose.yml`

Uses Strip Prefix in Nginx (`proxy_pass http://portainer:9000/`) — no internal URL base config needed.

---

### Cloudflared

Cloudflare Tunnel for external HTTPS access without port forwarding.

- **File:** `compose/cloudflared/docker-compose.yml`
- Get the tunnel token from: Cloudflare Zero Trust → Networks → Tunnels → your tunnel → Configure

```bash
# compose/cloudflared/.env  (create this — not committed)
CLOUDFLARE_TUNNEL_TOKEN=your_token_here
```

Or pass the token directly in the compose `command:` field (keep the compose file private if you do).

---

### Glances (System Stats)

System metrics API (CPU, RAM) consumed by the homepage dashboard.

- **Port:** `61208` — accessed from Nginx via Docker host gateway `172.17.0.1`
- **File:** `compose/glances/docker-compose.yml`

---

### Diskstats (Custom GPU + Disk API)

Custom Python server that exposes SSD/HDD usage and NVIDIA GPU stats to the dashboard.

- **Port:** `61209` — accessed from Nginx via `172.17.0.1`
- **Script:** `appdata/diskstats/server.py`
- **File:** `compose/diskstats/docker-compose.yml`

Endpoints:
- `GET /` → disk usage for `/mnt/e` and `/mnt/d` as JSON
- `GET /gpu` → GPU utilisation %, VRAM used/total, temperature

---

### Uptime Kuma

Service uptime monitoring.

- **Access:** `http://usnik-tuf:3001/` (direct)
- **File:** `compose/uptimekuma/docker-compose.yml`

---

### Homepage — Nginx Reverse Proxy

Custom static dashboard + Nginx SSL reverse proxy for all services.

- **Access:** `https://usnik-tuf/`
- **File:** `compose/homepage/docker-compose.yml`
- **Config:** `appdata/homepage/nginx.conf`
- **Dashboard:** `appdata/homepage/index.html`

The `project-tracker` sidecar is a static HTML container built from `project_plan/`:

```bash
cd /mnt/e/project_plan
docker build -t project-tracker:latest .
```

---

### Obsidian Remote

Browser-based Obsidian client — access the vault from any browser.

- **Access:** `https://usnik-tuf/obsidian/`
- **File:** `compose/obsidian/docker-compose.yml`
- The vault is mounted from `/mnt/e/usnik-vault` into the container at `/vault`

---

## Nginx Configuration Reference

**File:** `appdata/homepage/nginx.conf`

### Proxy patterns

| Pattern | Nginx syntax | When to use |
|---------|-------------|-------------|
| **Keep Prefix** | `proxy_pass http://service:port;` | App has an internal URL Base configured (Arrs, Jellyfin, Bazarr) |
| **Strip Prefix** | `proxy_pass http://service:port/;` | App serves at root, Nginx strips the subpath (Portainer) |

> **`proxy_set_header` inheritance gotcha:** If a `location` block defines *any* `proxy_set_header` directive (e.g. for WebSocket `Upgrade`), it stops inheriting **all** `proxy_set_header` directives from the parent `server` block. Always repeat `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` explicitly in WebSocket location blocks.

### Full config

```nginx
server {
    listen 80;
    server_name usnik-tuf-arch.tail25be85.ts.net usnik-tuf usnik-tuf-arch localhost;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name usnik-tuf-arch.tail25be85.ts.net usnik-tuf usnik-tuf-arch localhost;

    ssl_certificate /etc/nginx/ssl/master.crt;
    ssl_certificate_key /etc/nginx/ssl/master.key;

    # Standard proxy headers (inherited by simple location blocks)
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Ssl on;

    location / {
        root /usr/share/nginx/html;
        index index.html;
    }

    location /project-plan/ { proxy_pass http://project-tracker:80/; }

    location /obsidian/ {
        proxy_pass http://obsidian:3000/;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }

    # KEEP PREFIX — Jellyfin (BaseUrl=/jellyfin set in network.xml)
    location /jellyfin/ {
        proxy_pass http://jellyfin:8096;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location /qbittorrent/ {
        proxy_pass http://gluetun:8090/;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_redirect / /qbittorrent/;
    }

    # Jellyseerr — no subpath support, redirect to direct port
    location /jellyseerr/  { return 302 http://$host:5055/; }
    location = /jellyseerr { return 302 http://$host:5055/; }

    location /stash/ {
        proxy_pass http://gluetun:9999;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect / /stash/;
    }
    location /uptime/ {
        proxy_pass http://uptimekuma:3001;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_redirect / /uptime/;
    }

    # Arrs — Keep Prefix (URL Base set in each app)
    location /radarr/   { proxy_pass http://radarr:7878; }
    location /sonarr/   { proxy_pass http://sonarr:8989; }
    location /lidarr/   { proxy_pass http://lidarr:8686; }
    location /prowlarr/ { proxy_pass http://gluetun:9696; }
    location /bazarr/   { proxy_pass http://bazarr:6767; }

    # System
    location /portainer/ {
        proxy_pass http://portainer:9000/;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Canonical trailing-slash redirects
    location /jellyfin    { return 301 $scheme://$http_host/jellyfin/; }
    location /radarr      { return 301 $scheme://$http_host/radarr/; }
    location /sonarr      { return 301 $scheme://$http_host/sonarr/; }
    location /lidarr      { return 301 $scheme://$http_host/lidarr/; }
    location /prowlarr    { return 301 $scheme://$http_host/prowlarr/; }
    location /bazarr      { return 301 $scheme://$http_host/bazarr/; }
    location /portainer   { return 301 $scheme://$http_host/portainer/; }
    location /qbittorrent { return 301 $scheme://$http_host/qbittorrent/; }

    # Stats API (proxied from host gateway)
    location /stats/disks { proxy_pass http://172.17.0.1:61209/; }
    location /stats/gpu   { proxy_pass http://172.17.0.1:61209/gpu; }
    location /stats/      { proxy_pass http://172.17.0.1:61208/api/4/; }
}
```

---

## Service Access Table

| Service | Proxy URL | Direct | Notes |
|---------|-----------|--------|-------|
| Dashboard | `https://usnik-tuf/` | — | |
| Jellyfin | `https://usnik-tuf/jellyfin/` | `:8096` | BaseUrl in network.xml |
| Jellyseerr | redirects → | `:5055` | No subpath support |
| Radarr | `https://usnik-tuf/radarr/` | `:7878` | URL Base: /radarr |
| Sonarr | `https://usnik-tuf/sonarr/` | `:8989` | URL Base: /sonarr |
| Lidarr | `https://usnik-tuf/lidarr/` | `:8686` | URL Base: /lidarr |
| Prowlarr | `https://usnik-tuf/prowlarr/` | `:9696 (gluetun)` | URL Base: /prowlarr |
| Bazarr | `https://usnik-tuf/bazarr/` | `:6767` | base_url in config.yaml |
| qBittorrent | `https://usnik-tuf/qbittorrent/` | `:8090 (gluetun)` | Strip prefix |
| Portainer | `https://usnik-tuf/portainer/` | `:9000` | Strip prefix |
| Obsidian | `https://usnik-tuf/obsidian/` | — | Strip prefix |
| Uptime Kuma | `https://usnik-tuf/uptime/` | `:3001` | |
| Project Plan | `https://usnik-tuf/project-plan/` | — | Static container |

---

## Post-Install Configuration

Run through these in order after first deploying everything:

1. **Portainer** — create admin account
2. **Radarr / Sonarr / Lidarr** — Settings → General → URL Base → `/radarr`, `/sonarr`, `/lidarr`
3. **Prowlarr** — Settings → General → URL Base → `/prowlarr`, add indexers, connect to each arr
4. **qBittorrent** — change password, set download path to `/downloads`, allow host header for `usnik-tuf`
5. **Jellyfin** — run setup wizard, add libraries, enable NVENC, set BaseUrl via Admin → Networking
6. **Jellyseerr** — connect to Jellyfin (`http://jellyfin:8096`), connect Radarr + Sonarr
7. **Bazarr** — connect Radarr + Sonarr, add subtitle providers
8. **Cloudflared** — configure public hostname in Cloudflare Zero Trust dashboard

---

## Maintenance & Backup

### Commit config changes

```bash
cd /mnt/e
git add -A
git commit -m "config: describe what changed"
git push
```

### Update all containers

```bash
for dir in /mnt/e/compose/*/; do
  (cd "$dir" && docker compose pull && docker compose up -d)
done
```

### Renew the server certificate (every ~10 years)

```bash
cd /mnt/e/appdata/homepage/ssl
openssl genrsa -out master.key 2048
openssl req -new -key master.key -out master.csr -subj "/C=IN/O=UsnikHomelab/CN=usnik-tuf"
openssl x509 -req -in master.csr -CA MyLocalCA.crt -CAkey MyLocalCA.key \
  -CAcreateserial -out master.crt -days 3650 -sha256 -extfile ext.cnf
docker exec homepage nginx -s reload
```

### Reload Nginx without downtime

```bash
docker exec homepage nginx -s reload
```

### Check all container health

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```
