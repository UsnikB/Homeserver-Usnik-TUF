wsl -u root echo "WSL starting..." 2>$null

wsl -u root ip addr add 172.31.70.215/20 broadcast 172.31.79.255 dev eth0 label eth0:1 2>$null
exit 0