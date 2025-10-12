#!/bin/bash
# Script to initialize Mattermost with an admin account and skip first-run setup

# Set the environment variable to skip TLS verification
export MMCTL_INSECURE_TLS_CONNECTIONS=true
export MMCTL_LOCAL=true

# Wait for Mattermost to be fully up 
until curl -s http://localhost:8065/api/v4/system/ping | grep -q "OK"; do
    printf "Waiting for Mattermost to be fully up..."
    sleep 5
done
echo "Mattermost is up!"

# Mark the system as initialized to skip the setup wizard
echo "Configuring system to skip setup wizard..."
mmctl --local config set TeamSettings.EnableUserCreation true
mmctl --local config set TeamSettings.EnableOpenServer true
mmctl --local config set ServiceSettings.EnableTutorial false
mmctl --local config set ServiceSettings.EnableOnboardingFlow false
mmctl --local config set ServiceSettings.EnableDesktopLandingPage false

# Disable email notifications to prevent SMTP connection errors
echo "Disabling email notifications..."
mmctl --local config set EmailSettings.SendEmailNotifications false
mmctl --local config set EmailSettings.RequireEmailVerification false
mmctl --local config set EmailSettings.SendPushNotifications false

# Make a file to indicate initialization is complete
touch /tmp/mattermost_initialized

echo "Mattermost initialization complete."

