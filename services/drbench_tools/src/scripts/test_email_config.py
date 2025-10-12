#!/usr/bin/env python3
"""
Test script to verify email system configuration.

This script can be run inside a DrBench container to test:
1. Postfix configuration
2. Dovecot configuration  
3. Virtual mailbox mappings
4. Email sending/receiving capabilities
"""
import subprocess
import time
import sys
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status."""
    print(f"Testing: {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✓ {description}")
            if result.stdout.strip():
                print(f"  Output: {result.stdout.strip()}")
            return True
        else:
            print(f"✗ {description}")
            print(f"  Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ {description} (timeout)")
        return False
    except Exception as e:
        print(f"✗ {description} (exception: {e})")
        return False

def check_file_exists(filepath, description=""):
    """Check if a file exists."""
    path = Path(filepath)
    exists = path.exists()
    status = "✓" if exists else "✗"
    print(f"{status} File exists: {description} ({filepath})")
    return exists

def test_email_services():
    """Test email service configuration."""
    print("=== DrBench Email System Configuration Test ===\n")
    
    success_count = 0
    total_tests = 0
    
    # Test 1: Check if required files exist
    print("1. Configuration Files:")
    total_tests += 4
    if check_file_exists("/etc/postfix/main.cf", "Postfix main config"):
        success_count += 1
    if check_file_exists("/etc/dovecot/dovecot.conf", "Dovecot config"):
        success_count += 1
    if check_file_exists("/etc/postfix/virtual_mailboxes", "Virtual mailboxes"):
        success_count += 1
    if check_file_exists("/usr/share/roundcube/config/config.inc.php", "Roundcube config"):
        success_count += 1
    
    print()
    
    # Test 2: Check service status
    print("2. Service Status:")
    total_tests += 2
    if run_command("pgrep -f postfix", "Postfix running"):
        success_count += 1
    if run_command("pgrep -f dovecot", "Dovecot running"):
        success_count += 1
    
    print()
    
    # Test 3: Check Postfix configuration
    print("3. Postfix Configuration:")
    total_tests += 5
    if run_command("postconf virtual_mailbox_domains", "Virtual domains configured"):
        success_count += 1
    if run_command("postconf virtual_mailbox_maps", "Virtual mailbox maps configured"):
        success_count += 1
    if run_command("postconf mynetworks", "Network restrictions configured"):
        success_count += 1
    if run_command("postconf smtpd_relay_restrictions", "Relay restrictions configured"):
        success_count += 1
    if run_command("postconf myhostname", "Hostname configured"):
        success_count += 1
    
    print()
    
    # Test 4: Test mail delivery paths
    print("4. Mail System Paths:")
    total_tests += 2
    if check_file_exists("/var/mail", "Mail directory"):
        success_count += 1
    if run_command("ls -la /var/mail/", "Mail directory permissions"):
        success_count += 1
    
    print()
    
    # Test 5: Test SMTP connectivity
    print("5. SMTP Connectivity:")
    total_tests += 1
    if run_command("echo 'QUIT' | nc -w 5 localhost 25", "SMTP port accessible"):
        success_count += 1
    
    print()
    
    # Test 6: Test IMAP connectivity
    print("6. IMAP Connectivity:")
    total_tests += 1
    if run_command("echo 'A001 LOGOUT' | nc -w 5 localhost 143", "IMAP port accessible"):
        success_count += 1
    
    print()
    
    # Summary
    print("=== Test Summary ===")
    print(f"Passed: {success_count}/{total_tests} tests")
    
    if success_count == total_tests:
        print("🎉 All tests passed! Email system is properly configured.")
        return True
    else:
        print("⚠️  Some tests failed. Email system may need configuration adjustments.")
        return False

def show_configuration_details():
    """Show detailed configuration for debugging."""
    print("\n=== Configuration Details ===")
    
    print("\nPostfix Virtual Domains:")
    run_command("postconf virtual_mailbox_domains", "")
    
    print("\nPostfix Virtual Mailboxes:")
    if Path("/etc/postfix/virtual_mailboxes").exists():
        run_command("head -10 /etc/postfix/virtual_mailboxes", "")
    else:
        print("Virtual mailboxes file not found")
    
    print("\nDovecot Password File:")
    if Path("/etc/dovecot/passwd").exists():
        run_command("head -5 /etc/dovecot/passwd | cut -d: -f1", "Users (usernames only)")
    else:
        print("Dovecot password file not found")
    
    print("\nMail Directories:")
    run_command("ls -la /var/mail/ | head -10", "")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--details":
        show_configuration_details()
    else:
        success = test_email_services()
        if not success:
            print("\nFor detailed configuration info, run: python test_email_config.py --details")
        sys.exit(0 if success else 1)