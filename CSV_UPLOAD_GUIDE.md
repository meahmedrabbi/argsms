# CSV Upload System Guide

## Overview

The ARGSMS bot now uses a CSV-based system instead of web scraping for managing SMS ranges and phone numbers.

## CSV Format

Upload a CSV file with these columns:
- **Range** - Name of the SMS range (e.g., "Russia Lion Whatsapp 24 Oct")
- **Number** - Phone number (e.g., "79032454671")

**Other columns are ignored.**

### Example CSV:

```csv
Range,Number
Russia Lion Whatsapp 24 Oct,79032454671
Russia Lion Whatsapp 24 Oct,79393992881
Russia Lion Whatsapp 24 Oct,79995644839
UK Vodafone 21 Nov,447123456789
UK Vodafone 21 Nov,447123456790
```

## Admin Workflow

### 1. Upload CSV File

1. Open bot and type `/admin`
2. Click "📤 Upload CSV (Ranges & Numbers)"
3. Upload your CSV file
4. Bot will import ranges and numbers
5. You'll see a report: "✅ Successfully imported: X numbers"

### 2. Set Prices for Ranges

1. In admin panel, click "📋 Manage Ranges & Prices"
2. You'll see all uploaded ranges with current prices (default $1.00)
3. Click on a range to view details
4. Click "💰 Set Price"
5. Send the price (e.g., `1.50` or `0.50`)
6. Done!

### 3. Delete Ranges (Optional)

1. Go to range details
2. Click "🗑️ Delete Range"
3. Range and all its numbers will be deleted

## How It Works

### Range Unique IDs

Each range gets a unique ID (SHA-256 hash of range name). This means:
- Same range name = same range
- Numbers with same range name are grouped together
- Uploading same range again updates the numbers

### Number Management

- Duplicate numbers are handled automatically
- If a number exists, its range association is updated
- Numbers not in holds are available for users

### Number Hold System

When users request numbers, they are held temporarily:

**Expiration Rules:**
- **Initial hold**: 10 minutes from request time (if user never searches)
- **After first search**: 5 minutes from first SMS search attempt
- **Automatic cleanup**: Expired holds are released automatically

**Admin Controls:**
- **Analyze Holds**: View statistics and top users/ranges
- **Export Report**: Download Excel with all hold details
- **Cleanup Expired**: Manually trigger expiration cleanup
- **Release All**: Emergency button to free all temporary holds

**Why Numbers Get Held:**
- Users request 20 numbers → temporary holds created
- If users abandon search → holds expire after 10 minutes
- If users search for SMS → holds expire 5 minutes after first search
- If SMS received → hold becomes permanent (never expires)

### Price System

- Each range has one price
- Default price: $1.00
- Admin sets prices after uploading CSV
- Prices stored by range unique ID

## User Experience

Users see:
1. List of available ranges (from database)
2. Range details with available/held number counts
3. Request 20 random numbers from available pool
4. Numbers temporarily held (5-minute auto-release)
5. SMS checking (still uses original API)

## Database Tables

- **ranges** - SMS range information
- **phone_numbers** - Individual phone numbers linked to ranges
- **number_holds** - Tracks which numbers are held by users
- **price_ranges** - Prices for each range

## Re-uploading CSV

You can upload the same CSV multiple times:
- Existing ranges are reused (based on name)
- Existing numbers are updated if range changed
- New numbers are added
- Old numbers remain unless deleted

## Tips

1. **Organize by range name** - Use clear, consistent range names
2. **Set prices immediately** - After upload, set prices for all ranges
3. **Monitor holds** - Use "🔒 Number Holds Report" to see usage
4. **Regular updates** - Upload new CSV when you get new numbers

## Troubleshooting

**"❌ No SMS ranges available"**
- Admin needs to upload CSV first

**"❌ Not enough available numbers"**
- Too many numbers are held by users
- Use admin panel → "🔒 Number Holds Report" to analyze
- Options to fix:
  1. Wait for automatic expiration (10 min for abandoned requests)
  2. Click "🔄 Cleanup Expired Holds" to manually trigger cleanup
  3. Click "🔓 Release All Temporary Holds" to free everything (emergency)
  4. Upload more numbers via CSV

**Why are so many numbers held?**
- Users requested numbers but didn't search for SMS
- Old system: holds never expired without first_retry_time
- New system: holds expire after 10 minutes automatically
- Solution: Use "Release All" button or wait for automatic cleanup

**CSV import errors**
- Check CSV has "Range" and "Number" columns
- Ensure numbers are in correct format
- Check for special characters in range names

## Migration from Web Scraping

The bot no longer fetches ranges/numbers from the web panel. Instead:
- **Before:** Real-time API calls to external system
- **After:** CSV upload to local database

**Advantages:**
- No authentication issues
- Faster range browsing
- Better control over available numbers
- No network dependency for range listing
- Can track number usage precisely

**Note:** SMS message checking still uses the original API - only range/number management changed.
