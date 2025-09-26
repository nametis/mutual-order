import os
from requests_oauthlib import OAuth1Session
from urllib.parse import parse_qs


def main():
	consumer_key = os.environ.get('DISCOGS_CONSUMER_KEY')
	consumer_secret = os.environ.get('DISCOGS_CONSUMER_SECRET')
	callback_url = os.environ.get('DISCOGS_CALLBACK_URL', 'oob')

	if not consumer_key or not consumer_secret:
		print("Missing DISCOGS_CONSUMER_KEY or DISCOGS_CONSUMER_SECRET in environment.")
		return

	request_token_url = 'https://api.discogs.com/oauth/request_token'
	authorize_url = 'https://www.discogs.com/oauth/authorize'
	access_token_url = 'https://api.discogs.com/oauth/access_token'

	# Step 1: Obtain request token
	oauth = OAuth1Session(consumer_key, client_secret=consumer_secret, callback_uri=callback_url)
	fetch_response = oauth.fetch_request_token(request_token_url)
	resource_owner_key = fetch_response.get('oauth_token')
	resource_owner_secret = fetch_response.get('oauth_token_secret')

	# Step 2: Authorize
	authorization_url = oauth.authorization_url(authorize_url)
	print("Open this URL in your browser to authorize:")
	print(authorization_url)
	verifier = input("Enter the provided verifier (PIN): ").strip()

	# Step 3: Exchange for access token
	oauth = OAuth1Session(
		consumer_key,
		client_secret=consumer_secret,
		resource_owner_key=resource_owner_key,
		resource_owner_secret=resource_owner_secret,
		verifier=verifier,
	)
	access_tokens = oauth.fetch_access_token(access_token_url)

	access_token = access_tokens.get('oauth_token')
	access_secret = access_tokens.get('oauth_token_secret')

	print("\nAdd these to your .env or environment:")
	print(f"DISCOGS_ACCESS_TOKEN={access_token}")
	print(f"DISCOGS_ACCESS_SECRET={access_secret}")

	print("\nTip: ensure Discogs buyer settings currency is set to EUR.")


if __name__ == '__main__':
	main()



