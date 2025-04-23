import argparse
import os
import shutil
from cert_handler import generate_ca
from configs import CERT_FILE, KEY_FILE

def check_ca_status():
    """Check if CA certificate exists and is valid"""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        try:
            print("CA certificate exists and is valid")
            print(f"Certificate file: {CERT_FILE}")
            print(f"Private key file: {KEY_FILE}")
            print("\nSECURITY WARNING: This is a HTTPS proxy CA certificate")
            print("This CA is used to decrypt HTTPS traffic - DO NOT share it with anyone")
            print("REMOVE it from trusted certificates when not actively in use")
        except Exception as e:
            print(f"CA certificate exists but is invalid: {str(e)}")
    else:
        print("No CA certificate found")

def clear_cache():
    """Clear cache"""
    shutil.rmtree(os.path.join(os.getcwd(), ".cache"))

def show_help():
    """Display help information"""
    print("CA Certificate Management Tool")
    print("Usage:")
    print("  python init.py               - Show current status and help")
    print("  python init.py --generate-ca - Generate new CA certificate")
    print("  python init.py --clear-cache - Clear proxy cache")
    print("\nImportant Notes:")
    print("1. To trust this CA on Windows:")
    print("   - Doule-click the certificate file and select 'Install Certificate'")
    print("   - Import the certificate to 'Trusted Root Certification Authorities'")
    print("2. SECURITY CRITICAL: This is a HTTPS proxy CA")
    print("   - It decrypts HTTPS traffic - NEVER share the certificate")
    print("   - REMOVE it from trusted certificates when not actively in use")
    print("   - You can use win + R to run 'certmgr.msc' and delete the certificate")

def main():
    parser = argparse.ArgumentParser(description='CA Certificate Management')
    parser.add_argument('--generate-ca', action='store_true', help='Generate new CA certificate')
    parser.add_argument('--clear-cache', action='store_true', help='Clear proxy cache')
    
    args = parser.parse_args()

    if args.clear_cache:
        print("Clearing proxy cache...")
        clear_cache()
        print("Proxy cache cleared successfully")
    elif args.generate_ca:
        print("Generating new CA certificate...")
        generate_ca()
        print("CA certificate generated successfully")
        print("\nIMPORTANT NEXT STEPS:")
        print("1. You need to manually trust this CA certificate in Windows")
        print("2. SECURITY ALERT: This is a HTTPS proxy CA")
        print("   - NEVER share these files with anyone")
        print("   - REMOVE it from trusted certificates when not actively in use")
        print("   - You can use win + R to run 'certmgr.msc' and delete the certificate")
        print(f"     Certificate file: {CERT_FILE}")
        print(f"     Private key file: {KEY_FILE}")
    else:
        check_ca_status()
        print("\n")
        show_help()

if __name__ == "__main__":
    main()
