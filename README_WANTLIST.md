# Wantlist Feature Implementation

This document describes the wantlist feature implementation for the Mutual Order application.

## Overview

The wantlist feature allows users to:
1. Sync their Discogs wantlist to the local database
2. Find references to their wantlist items in seller listings
3. Get statistics about their wantlist and references
4. Manage their wantlist items and references

## Architecture

### Database Models

#### WantlistItem
- Stores individual items from a user's Discogs wantlist
- Fields: `id`, `user_id`, `discogs_want_id`, `release_id`, `title`, `artists`, `year`, `format`, `thumb_url`, `date_added`, `last_checked`, `created_at`
- Unique constraint on `(user_id, discogs_want_id)`

#### WantlistReference
- Links wantlist items to seller listings
- Fields: `id`, `wantlist_item_id`, `listing_id`, `user_id`, `match_confidence`, `created_at`
- Unique constraint on `(wantlist_item_id, listing_id)`

### Services

#### WantlistService
- `sync_user_wantlist(user_id, force_refresh=False)`: Syncs user's wantlist from Discogs
- `get_user_wantlist(user_id)`: Gets user's wantlist from local database
- `find_references_in_listings(user_id, order_id=None)`: Finds references in seller listings
- `get_wantlist_stats(user_id)`: Gets statistics about wantlist and references
- `cleanup_old_references(days=30)`: Cleans up old references

### API Endpoints

#### `/api/wantlist/sync` (POST)
- Syncs user's wantlist from Discogs
- Parameters: `force_refresh` (optional)
- Returns: List of synced wantlist items

#### `/api/wantlist` (GET)
- Gets user's wantlist from local database
- Returns: List of wantlist items

#### `/api/wantlist/references` (GET)
- Gets references to user's wantlist items in seller listings
- Parameters: `order_id` (optional)
- Returns: List of references

#### `/api/wantlist/stats` (GET)
- Gets statistics about user's wantlist and references
- Returns: Statistics object

#### `/api/wantlist/references/<listing_id>` (GET)
- Gets wantlist references for a specific listing
- Returns: List of references for the listing

#### `/api/wantlist/cleanup` (POST)
- Cleans up old wantlist references (admin only)
- Parameters: `days` (optional, default 30)
- Returns: Number of deleted references

#### `/api/wantlist/item/<item_id>` (DELETE)
- Deletes a wantlist item
- Returns: Success message

#### `/api/wantlist/reference/<reference_id>` (DELETE)
- Deletes a wantlist reference
- Returns: Success message

## Installation and Setup

### 1. Database Migration
Run the migration script to add the new tables:

```bash
python scripts/migrate_wantlist.py
```

### 2. Test the Implementation
Run the test script to verify everything works:

```bash
python scripts/test_wantlist.py
```

### 3. Environment Variables
Ensure these environment variables are set:
- `DISCOGS_CONSUMER_KEY`
- `DISCOGS_CONSUMER_SECRET`
- `DISCOGS_ACCESS_TOKEN`
- `DISCOGS_ACCESS_SECRET`

## Usage

### For Users
1. **Sync Wantlist**: Call `/api/wantlist/sync` to sync your Discogs wantlist
2. **View Wantlist**: Call `/api/wantlist` to view your local wantlist
3. **Find References**: Call `/api/wantlist/references` to find references in seller listings
4. **View Stats**: Call `/api/wantlist/stats` to see statistics

### For Developers
1. **Add to Frontend**: Create UI components to display wantlist and references
2. **Real-time Updates**: Consider adding WebSocket support for real-time updates
3. **Caching**: The service uses Redis caching for performance
4. **Rate Limiting**: Respects Discogs API rate limits (25 calls/minute)

## Matching Algorithm

The system uses a confidence-based matching algorithm to find references:

1. **Title Similarity** (60% weight): Uses `difflib.SequenceMatcher` to compare titles
2. **Artist Matching** (30% weight): Checks if any artist from wantlist appears in listing title
3. **Year Matching** (10% weight): Compares years (within 1 year tolerance)

Matches with confidence > 0.7 are considered valid references.

## Performance Considerations

- **Caching**: Wantlist data is cached for 30 minutes
- **Rate Limiting**: Discogs API calls are rate-limited to 25/minute
- **Batch Processing**: References are found in batches to avoid memory issues
- **Cleanup**: Old references are automatically cleaned up

## Error Handling

- All API endpoints return proper HTTP status codes
- Errors are logged for debugging
- Database transactions are properly rolled back on errors
- Graceful degradation when Discogs API is unavailable

## Future Enhancements

1. **Real-time Notifications**: Notify users when new references are found
2. **Advanced Matching**: Use machine learning for better matching
3. **Bulk Operations**: Support for bulk wantlist operations
4. **Export/Import**: Allow users to export/import wantlist data
5. **Analytics**: More detailed analytics and reporting

## Troubleshooting

### Common Issues

1. **Discogs API Errors**: Check API credentials and rate limits
2. **Database Errors**: Ensure migration was run successfully
3. **Memory Issues**: Consider reducing batch sizes for large wantlists
4. **Performance**: Check Redis cache configuration

### Debug Commands

```bash
# Check database tables
python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); print(db.inspect(db.engine).get_table_names())"

# Test wantlist service
python scripts/test_wantlist.py

# Check logs
tail -f logs/app.log
```

## Security Considerations

- All endpoints require authentication
- Admin-only endpoints are properly protected
- User data is properly isolated
- SQL injection protection through SQLAlchemy ORM
- Input validation on all API endpoints
