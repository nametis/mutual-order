import os
import sys

def main():
	# Lazy import inside to ensure Flask app loads with env
	from app import get_app
	from services import discogs_service

	if len(sys.argv) < 2:
		print("Usage: python -m scripts.fetch_listing <listing_url_or_id>")
		sys.exit(1)

	arg = sys.argv[1]
	listing_id = None

	# Accept full URL or numeric id
	if arg.isdigit():
		listing_id = arg
	else:
		listing_id = discogs_service.extract_listing_id(arg)

	if not listing_id:
		print("Could not extract listing id. Provide a numeric id or Discogs listing URL.")
		sys.exit(1)

	app = get_app()
	with app.app_context():
		try:
			data = discogs_service.fetch_listing_data(listing_id)
			print({
				'id': data['id'],
				'price_value': data['price_value'],
				'currency': data['currency']
			})
		except Exception as e:
			print(f"Error: {e}")
			sys.exit(2)

if __name__ == '__main__':
	main()

