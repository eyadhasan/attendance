
import uvicorn
import sys
import os
from pyngrok import ngrok, conf

def start_share():
    # 1. Start ngrok tunnel
    print("Initializing ngrok tunnel...")
    
    # Check if auth token is configured, if not, try to ask or warn
    # We can try to connect, if it fails due to auth, we catch it.
    
    public_url = None
    try:
        # Create a tunnel to port 8000
        # bind_tls=True ensures we get an https URL
        public_url = ngrok.connect(8000, bind_tls=True).public_url
    except Exception as e:
        error_msg = str(e)
        if "ERR_NGROK_4018" in error_msg or "authentication failed" in error_msg.lower():
            print("\n" + "!"*60)
            print("AUTHENTICATION ERROR: You need a free ngrok account.")
            print("!"*60)
            print("1. Go to https://dashboard.ngrok.com/signup and login.")
            print("2. Copy your Authtoken from https://dashboard.ngrok.com/get-started/your-authtoken")
            print("-" * 30)
            
            token = input("Paste your Authtoken here and press Enter: ").strip()
            
            if token:
                try:
                    # Set the token
                    ngrok.set_auth_token(token)
                    # Try again
                    public_url = ngrok.connect(8000, bind_tls=True).public_url
                except Exception as retry_e:
                    print(f"\nFailed again: {retry_e}")
                    sys.exit(1)
            else:
                print("No token provided. Exiting.")
                sys.exit(1)
        else:
            print(f"\nError starting ngrok: {e}")
            sys.exit(1)

    if public_url:
        print(f"\n{'='*60}")
        print(f"🌍 PUBLIC URL: {public_url}")
        print(f"👉 Share this URL with your mobile developer!")
        print(f"   API Docs: {public_url}/docs")
        print(f"   Register Endpoint: {public_url}/register")
        print(f"{'='*60}\n")
    
    # 2. Start the FastAPI server
    try:
        print("Starting FastAPI server...")
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
    except KeyboardInterrupt:
        print("\nStopping server...")
        ngrok.kill()

if __name__ == "__main__":
    start_share()
