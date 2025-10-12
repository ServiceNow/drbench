#!/bin/bash
# vnc-setup.sh - Simplified VNC server setup for Docker containers

# Set environment variables
export DISPLAY=:1
# Use environment variables or default to root if not set
export USER=${VNC_USER:-root}
if [ -n "$VNC_USER" ]; then
    if [ "$VNC_USER" = "root" ]; then
        HOME="/root"
    else
        HOME="/home/$VNC_USER"
    fi
else
    # Default to root if VNC_USER is not set
    HOME="/root"
fi
export HOME

# Ensure directories exist
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix

# Remove any existing lock files
rm -f /tmp/.X1-lock
rm -f /tmp/.X11-unix/X1

# Start Xvfb
Xvfb :1 -screen 0 1280x800x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
echo "Started Xvfb with PID: $XVFB_PID"
sleep 2

# Setup VNC password
mkdir -p $HOME/.vnc
echo "vnc_pwd" | vncpasswd -f > $HOME/.vnc/passwd
chmod 600 $HOME/.vnc/passwd

# Start VNC server
x11vnc -display :1 -forever -shared -rfbauth $HOME/.vnc/passwd -geometry 1280x800 -rfbport 5901 -noxdamage -bg
echo "Started VNC server on port 5901"

# Start XFCE session components
echo "Starting window manager..."
xfwm4 --replace --compositor=off &
XFWM_PID=$!
sleep 2

echo "Starting desktop..."
xfdesktop &
DESKTOP_PID=$!
sleep 1

echo "Starting panel..."
xfce4-panel &
PANEL_PID=$!

# Create Firefox profile with disabled welcome page
mkdir -p $HOME/.mozilla/firefox/drbench.default
cat > $HOME/.mozilla/firefox/drbench.default/user.js << EOL
// Disable welcome page
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("startup.homepage_welcome_url.additional", "");
user_pref("startup.homepage_override_url", "");
// Set homepage to blank page
user_pref("browser.startup.homepage", "about:blank");
// Disable browser tabs welcome page
user_pref("browser.startup.firstrunSkipsHomepage", true);
// Disable default browser check
user_pref("browser.shell.checkDefaultBrowser", false);
// Disable What's New page
user_pref("browser.messaging-system.whatsNewPanel.enabled", false);
EOL

# Create Firefox profiles.ini
mkdir -p $HOME/.mozilla/firefox
cat > $HOME/.mozilla/firefox/profiles.ini << EOL
[Profile0]
Name=drbench
IsRelative=1
Path=drbench.default
Default=1
EOL

# Create Firefox desktop shortcut
mkdir -p $HOME/Desktop
cat > $HOME/Desktop/Firefox.desktop << EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Firefox Web Browser
Comment=Browse the World Wide Web
Exec=firefox-esr -P drbench %u
Icon=firefox-esr
Terminal=false
Categories=Network;WebBrowser;
EOL
chmod +x $HOME/Desktop/Firefox.desktop

echo "VNC server successfully started"
# echo "Access with VNC client at port 5901 with password: vnc_pwd"
# echo "Or use noVNC web client at port 6080"

# Keep script running to keep the session alive
echo "Monitoring X11 server process $XVFB_PID"
wait $XVFB_PID
