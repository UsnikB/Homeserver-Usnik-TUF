# Homelab Documentation

This file serves as a shared source of truth for all AI/CLI agents (Gemini, Claude, etc.) interacting with this homelab.

## 🛠️ System Overview
- **User:** usnik (Usnik-TUF)
- **Timezone:** Asia/Kolkata (IST)
- **Host OS:** Windows with Arch Linux WSL2
- **Shell:** bash

## 💻 Hardware (ASUS TUF Laptop)
- **CPU:** AMD Ryzen 7 4800H (8C/16T)
- **GPU:** NVIDIA GeForce GTX 1660 Ti (Used for Jellyfin NVENC transcoding)
- **RAM:** 8GB (approx. 7.47 GiB total, 2 GiB swap)

## 📁 Storage Layout
| Mount | Physical Disk | Primary Use |
|-------|---------------|-------------|
| `/mnt/e` | SSD | **Working Dir:** Docker configs (`appdata`), compose files, and active downloads. |
| `/mnt/d` | HDD | **Media Storage:** Final library for Movies, TV, Music. |

**Key Paths:**
- Root Dir: `/mnt/e/`
- Docker Compose: `/mnt/e/compose/arr/docker-compose.yml`
- Appdata: `/mnt/e/appdata/`
- Downloads: `/mnt/e/downloads/` (Moved to SSD to prevent disk bottleneck for Jellyfin)
- Media: `/mnt/d/media/` (Movies, TV, Music)

## 🐳 Docker Stack (Servarr Stack)
Managed via Docker Desktop. All services on `arr-network` bridge unless specified.

| Service | Port | VPN? | Role |
|---------|------|------|------|
| **Gluetun** | - | Yes | **VPN Gateway:** PIA OpenVPN (Pointed to Netherlands) |
| **qBittorrent** | 8090 | Yes | Torrent client (network_mode: service:gluetun) |
| **Prowlarr** | 9696 | Yes | Indexer management (network_mode: service:gluetun) |
| **Jellyfin** | 8096 | No | Media Server (NVIDIA GPU acceleration enabled) |
| **Jellyseerr** | 5055 | No | Media Requests |
| **Radarr** | 7878 | No | Movie automation |
| **Sonarr** | 8989 | No | TV automation |
| **Lidarr** | 8686 | No | Music automation |
| **Bazarr** | 6767 | No | Subtitle management |
| **Portainer** | 9000 | No | Docker UI management |
| **Uptime Kuma** | 3001 | No | Monitoring |
| **Cloudflared** | - | No | External access tunnel |
| **Homepage** | 80 | No | Dashboard with system stats backend (:61209) |

## 📝 Operating Procedures
1. **Approval:** Always ask the user before making non-documentation changes (any file modification that isn't `.md`).
2. **Analysis:** Read-only analysis of the system is encouraged and does not require pre-approval.
3. **Troubleshooting:** If VPN-linked services (qBittorrent, Prowlarr) are down, check the `gluetun` container health and logs first.
4. **Maintenance:** Keep appdata and compose files in `/mnt/e`.

---
*Last updated by Gemini CLI on April 9, 2026*
