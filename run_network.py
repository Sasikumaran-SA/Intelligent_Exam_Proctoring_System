import socket
import os
import subprocess
import time

def get_local_ip():
    """Returns the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        s.connect(('8.8.8.8', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    local_ip = get_local_ip()
    backend_port = 8000
    frontend_port = 6300

    print("=" * 60)
    print("      EXAM PROCTORING SYSTEM - NETWORK ACCESS HELPER")
    print("=" * 60)
    print(f"\n[Environment: dl-pro]")
    print(f"\nYour Local IP Address: {local_ip}")
    print("\nShare these URLs with other laptops on your Wi-Fi:")
    print("-" * 60)
    print(f" STUDENT PORTAL:  http://{local_ip}:{frontend_port}")
    print(f" ADMIN DASHBOARD: http://{local_ip}:{frontend_port}/admin")
    print("-" * 60)
    print(f"\nBACKEND API (Ref only): http://{local_ip}:{backend_port}")
    print("\n" + "!" * 60)
    print(" IMPORTANT: WINDOWS FIREWALL CHECK")
    print(" If other laptops cannot connect, you must allow ports 6300 and 8000")
    print(" through your Windows Defender Firewall.")
    print("!" * 60)
    
    print("\nStarting Backend Server on 0.0.0.0:8000...")
    print("Press Ctrl+C to stop.\n")
    
    # Change to backend directory and run
    try:
        os.chdir("backend")
        subprocess.run(["python", "main.py"])
    except KeyboardInterrupt:
        print("\nStopping server...")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    main()
