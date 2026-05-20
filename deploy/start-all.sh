#!/bin/bash
# Autostart wszystkich aplikacji po restarcie serwera

sleep 10  # czekaj aż system się załaduje

# Tristate Tools (port 40152)
screen -dmS tristate bash -c 'cd /home/claude-runner/tristate-tools/backend && node server.js 2>&1 | tee /tmp/tristate.log'

# Business Analyzer (port 40153)
screen -dmS business bash -c 'cd /home/claude-runner/business-analyzer/backend && node server.js >> /home/claude-runner/business-analyzer/server.log 2>&1'

# AI Trading System + Kalshi Evo — zarządzane przez systemd (auto-restart)
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start trading.service
XDG_RUNTIME_DIR=/run/user/$(id -u) systemctl --user start kalshi.service

echo "$(date) — wszystkie aplikacje uruchomione" >> /home/claude-runner/autostart.log
