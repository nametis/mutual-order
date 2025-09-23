# Script à exécuter une seule fois pour renouveler les tokens
# Mettre dans un fichier séparé (ex: renew_tokens.py)

from requests_oauthlib import OAuth1Session
import os
from dotenv import load_dotenv

load_dotenv()

CONSUMER_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')

def renew_discogs_tokens():
    """Renouveler les tokens statiques pour l'application"""
    
    # Étape 1: Obtenir le request token
    request_token_url = 'https://api.discogs.com/oauth/request_token'
    oauth = OAuth1Session(CONSUMER_KEY, client_secret=CONSUMER_SECRET)
    
    try:
        fetch_response = oauth.fetch_request_token(request_token_url)
        request_token = fetch_response.get('oauth_token')
        request_token_secret = fetch_response.get('oauth_token_secret')
        
        print(f"Request Token: {request_token}")
        print(f"Request Token Secret: {request_token_secret}")
        
        # Étape 2: URL d'autorisation
        authorization_url = 'https://www.discogs.com/oauth/authorize'
        authorize_url = f"{authorization_url}?oauth_token={request_token}"
        
        print(f"\n1. Allez sur cette URL et autorisez l'application:")
        print(f"{authorize_url}")
        
        print(f"\n2. Après autorisation, entrez le verifier code:")
        verifier = input("Verifier code: ")
        
        # Étape 3: Échanger contre les access tokens
        access_token_url = 'https://api.discogs.com/oauth/access_token'
        oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=request_token,
            resource_owner_secret=request_token_secret,
            verifier=verifier
        )
        
        oauth_tokens = oauth.fetch_access_token(access_token_url)
        access_token = oauth_tokens.get('oauth_token')
        access_token_secret = oauth_tokens.get('oauth_token_secret')
        
        print(f"\n✅ Nouveaux tokens générés:")
        print(f"DISCOGS_ACCESS_TOKEN={access_token}")
        print(f"DISCOGS_ACCESS_SECRET={access_token_secret}")
        
        print(f"\n📝 Mettez à jour votre .env avec ces nouvelles valeurs")
        
        # Test des nouveaux tokens
        test_oauth = OAuth1Session(
            CONSUMER_KEY,
            client_secret=CONSUMER_SECRET,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret
        )
        
        test_response = test_oauth.get('https://api.discogs.com/oauth/identity')
        if test_response.status_code == 200:
            identity = test_response.json()
            print(f"\n✅ Test réussi - Connecté comme: {identity.get('username')}")
        else:
            print(f"\n❌ Erreur test: {test_response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == "__main__":
    renew_discogs_tokens()