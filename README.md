# Facebook Ad Library Scraper (Python)

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Last verified](https://img.shields.io/badge/last%20verified-2026--10--17-brightgreen.svg)](#how-we-keep-it-working)

Scrape the public Meta (Facebook) Ad Library with Python: ads by keyword, all ads of one advertiser, ad videos and images, as JSON or CSV. No login, no API token, one file.

> **Need this at scale?** The script is for learning and small jobs. The [ToolzerHub Meta Ad Library API](https://toolzerhub.com/apis/meta-ads?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper) returns the same ads and more (up to 50 ads per call, filters for language, ad type and reach, sorting by impressions, advertiser lookup by name or URL) as JSON from any server, with no blocks to handle. 100 free credits a month, no card needed.

## What it scrapes

| Command | What you get |
|---|---|
| `search <keyword>` | Ads that match a keyword, in any country, with `--active` or `--all`, media type, platform and start-date filters, paged with `--limit` |
| `page <page id, URL or username>` | Every ad one advertiser runs, paged with `--limit` |
| `pages <name>` | Advertiser pages that match a name, with their page ids, likes and Instagram handle |
| `ad <ad id> --page <page>` | One ad with its details: advertiser info, takedown flag and, where Meta publishes it, audience and EU reach |

`search` and `page` also take `--csv` (a spreadsheet) and `--download DIR` (saves the ad videos and images).

## Quick start

```bash
git clone https://github.com/toolzerhub/facebook-ad-library-scraper.git
cd facebook-ad-library-scraper
pip install -r requirements.txt
python facebook_ad_library_scraper.py pages duolingo
```

More examples:

```bash
python facebook_ad_library_scraper.py search nike --limit 20 -o ads.json
python facebook_ad_library_scraper.py search "running shoes" --country GB --media video --all
python facebook_ad_library_scraper.py page duolingo --limit 50 -o duolingo-ads.json
python facebook_ad_library_scraper.py page https://www.facebook.com/duolingo --csv -o duolingo-ads.csv
python facebook_ad_library_scraper.py ad 1465647328763769 --page duolingo
```

Download the videos and images of an advertiser's ads:

```bash
python facebook_ad_library_scraper.py page duolingo --limit 10 --download ads/
```

Every command takes `-o file` to save the result and `--proxy URL` to route through a proxy. The script also reads `HTTPS_PROXY`.

Useful flags for `search` and `page`:

| Flag | Meaning |
|---|---|
| `--country US` | Two-letter country code, or `ALL`. Default `US` |
| `--active` / `--all` | Only ads running now (default), or running and ended ads |
| `--media video` | `all`, `image`, `video` or `meme` |
| `--platform INSTAGRAM` | Only ads shown on that platform. Repeat for more |
| `--date-min 2026-09-01`, `--date-max ...` | Ads that started in that window |
| `--exact` | `search` only: match the exact phrase |
| `--limit 20` | How many ads to return. Default 20 |

If a search returns nothing, try `--all` or another `--country`.

## Example output

`python facebook_ad_library_scraper.py page duolingo --limit 3` (one ad shown; URLs shortened, lists cut to one item)

```json
{
  "ad_archive_id": "1731837484568780",
  "ad_url": "https://www.facebook.com/ads/library/?id=1731837484568780",
  "page_id": "141935472517297",
  "page_name": "Duolingo",
  "page_url": "https://facebook.com/duolingo",
  "page_likes": 2395310,
  "page_categories": ["App page"],
  "is_active": true,
  "start_date": "2026-10-14T07:00:00+00:00",
  "end_date": "2026-10-17T07:00:00+00:00",
  "platforms": ["FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK", "THREADS"],
  "countries": [],
  "ad_text": "Learn a language for free with fun lessons designed to keep you motivated!",
  "title": "Free Language Learning",
  "link_description": null,
  "cta_text": "Install now",
  "cta_type": "INSTALL_MOBILE_APP",
  "link_url": "http://play.google.com/store/apps/details?id=com.duolingo",
  "display_format": "DCO",
  "media_type": "video",
  "image_urls": [],
  "videos": [
    {
      "hd_url": "https://video-msp1-1.xx.fbcdn.net/o1/v/t2/f2/m366/AQNqdzgO2PgyAeVrtzRT...",
      "sd_url": "https://video-msp1-1.xx.fbcdn.net/o1/v/t2/f2/m412/AQNj18R6rzLs0nnCs4U-...",
      "preview_url": "https://scontent-msp1-1.xx.fbcdn.net/v/t39.35426-6/845881816_189189784..."
    }
  ],
  "cards": [
    {
      "title": "Free Language Learning",
      "text": "Learn a language for free with fun lessons designed to keep you motivated!",
      "link_url": "http://play.google.com/store/apps/details?id=com.duolingo",
      "cta_text": "Install Now"
    }
  ],
  "variants": 1,
  "impressions": null,
  "spend_min": null,
  "spend_max": null,
  "currency": null,
  "reach_min": null,
  "reach_max": null
}
```

`python facebook_ad_library_scraper.py pages duolingo --limit 3` (one shown)

```json
[
  {
    "page_id": "141935472517297",
    "name": "Duolingo",
    "url": "https://www.facebook.com/duolingo/",
    "alias": "duolingo",
    "category": "App page",
    "likes": 2395310,
    "is_verified": true,
    "instagram_username": "duolingo",
    "instagram_followers": 5364826,
    "is_deleted": false,
    "image_url": "https://scontent-mia5-1.xx.fbcdn.net/v/t39.30808-1/838940116_153933447..."
  }
]
```

Full outputs for every command, plus a CSV, are in [examples/](examples).

## Fields

### search and page

| Field | Description |
|---|---|
| ad_archive_id | The ad's id in the Ad Library |
| ad_url | Link to the ad in the Ad Library |
| page_id, page_name, page_url | The advertiser |
| page_likes, page_categories | Page likes and categories |
| is_active | Whether Meta lists the ad as running |
| start_date, end_date | ISO 8601 UTC. Meta dates ads at midnight Pacific time, so these land at 07:00 or 08:00 UTC. For running ads `end_date` is the latest date Meta shows |
| platforms | `FACEBOOK`, `INSTAGRAM`, `AUDIENCE_NETWORK`, `MESSENGER`, `THREADS` |
| countries | Countries Meta says the ad reached. Filled mostly for ads shown in the EU and UK |
| ad_text | Ad body text. Catalog ads can show a template such as `{{product.brand}}` here; the text people see is in `cards` |
| title, link_description | Headline and link description |
| cta_text, cta_type | Button label and its type, such as `SHOP_NOW` |
| link_url | Where the ad sends people |
| display_format | Meta's format name: `IMAGE`, `VIDEO`, `CAROUSEL`, `DCO`, `DPA` |
| media_type | `video`, `image`, `carousel` or `none` |
| image_urls | Image URLs (signed; they expire after about five days) |
| videos | Videos as `hd_url`, `sd_url` and `preview_url`. `hd_url` is null when Meta has only the SD file |
| cards | The ad's cards (carousel and catalog items): title, text, link and button |
| variants | How many near-identical copies Meta grouped under this ad |
| impressions, spend_min, spend_max, currency, reach_min, reach_max | Meta's ranges, when it publishes them (see Limits) |
| downloaded | With `--download`: the files saved for this ad |

### pages

| Field | Description |
|---|---|
| page_id | The id to use with `page` and `ad` |
| name, alias, url | Page name, handle and link |
| category, likes, is_verified | Page category, likes, blue badge |
| instagram_username, instagram_followers | The linked Instagram account |
| is_deleted | Whether the page was deleted |
| image_url | Profile picture URL |

### ad

The same fields as `search`, plus `details`:

| Field | Description |
|---|---|
| details.page_about, page_category, page_is_verified | The advertiser |
| details.instagram_username, instagram_followers | The linked Instagram account |
| details.is_taken_down, violation_types | Takedown flag and reasons, when Meta lists them |
| details.audience_country, audience_age_gender, audience_regions | Share of the audience by age, gender and region (only where Meta publishes it) |
| details.eu_total_reach, eu_age_country_gender | Reach in the EU, by country, age and gender |
| details.page_lifetime_spend | Lifetime spend of the page, by payer name |

## How it works

1. It sends the same GraphQL queries the Ad Library website sends, as Chrome would. [curl_cffi](https://github.com/lexiforest/curl_cffi) matches the browser's TLS fingerprint. Facebook gives a guest cookie to any visitor on the first reply; there is nothing to log in to.
2. `search` and `page` use the library's search query. Meta returns 10 ads per request, so the script follows the cursor until it has `--limit` ads. `pages` uses the library's search box query. A page URL or username becomes a numeric page id by reading the page's public HTML.
3. The answer is cleaned into the fields above. Dates become ISO 8601, counts become integers, and the media sits in `image_urls` and `videos` whichever list Meta used. `--download` then fetches those files.

Further reading: [download Meta Ad Library videos](https://toolzerhub.com/blog/download-meta-ad-library-videos?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper), [Facebook Ad Library API in Python](https://toolzerhub.com/blog/facebook-ad-library-api-python?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper) and [the Meta Ad Library API explained](https://toolzerhub.com/blog/meta-ad-library-api?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper).

## Limits

- Public data only: what the Ad Library shows to a visitor without an account.
- Keyword search returns ads from many advertisers that mention the word, not only the brand. To get a brand's own ads, find its page with `pages`, then use `page`.
- Spend, impressions and reach are mostly empty. Meta publishes them for political and issue ads and for ads shown in the EU and UK, as ranges. The `ad` audience fields follow the same rule.
- `ad` needs the advertiser page too. It looks for the ad in the first `--scan` pages (300 ads) of that advertiser, so for a very busy page raise `--scan`.
- Video and image URLs are signed and expire after about five days. Download soon, or use `--download`.
- Meta caps a request at 10 ads, so big pulls take many requests.
- Facebook blocks most cloud and datacenter IPs, usually with a redirect, HTTP 403 or a rate-limit error. Run it from a home connection, or pass `--proxy` (a sticky residential proxy works best).
- No retries, no concurrency. That is on purpose: the script stays short enough to read in one sitting.
- It breaks when Facebook changes its pages. The query ids (`DOC_*` at the top of the script) change every few months; that is the usual cause.

## Scaling up

The script is for learning and small jobs. At scale you run into blocks, changing query ids and proxy costs. The [ToolzerHub Meta Ad Library API](https://toolzerhub.com/apis/meta-ads?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper) handles all of that:

| | This script | ToolzerHub API |
|---|---|---|
| Data | Keyword search, page ads, advertiser search, one ad, video and image download, CSV | 8 endpoints: ad search, page ads by id or URL, ad details, advertiser search, page-id lookup, filter options, Ad Library link parser. Up to 50 ads per call, language, ad type and reach filters, sort by impressions |
| Blocks and proxies | Your problem | Handled |
| When Facebook changes | Wait for a fix here | Fixed on our side |
| Cost | Free, plus your proxy | 100 free credits a month, then from $0.99 per 1,000 calls |

## How we keep it working

Every command is run against live Facebook Ad Library pages before each update, and the "last verified" badge shows the last day they all passed. If something breaks, [open an issue](https://github.com/toolzerhub/facebook-ad-library-scraper/issues).

## FAQ

**Is scraping the Facebook Ad Library legal?**
Scraping publicly available data is generally allowed in many places, but it depends on your country, what you collect and how you use it. Read the Legal section below.

**Why am I getting "blocked or rate-limited"?**
Facebook blocks most cloud and datacenter IP addresses. Use a home connection or a residential proxy, and slow down.

**Can it filter by language or ad type, or sort by impressions?**
No. The [ToolzerHub API](https://toolzerhub.com/apis/meta-ads?utm_source=github&utm_medium=readme&utm_campaign=facebook-ad-library-scraper) can.

## Related scrapers

- [instagram-scraper](https://github.com/toolzerhub/instagram-scraper): public Instagram profiles, posts, comments and search
- [tiktok-scraper](https://github.com/toolzerhub/tiktok-scraper): public TikTok profiles, videos, comments and hashtags
- [threads-scraper](https://github.com/toolzerhub/threads-scraper): public Threads profiles, posts, replies and search
- [reddit-scraper](https://github.com/toolzerhub/reddit-scraper): public subreddits, posts, comments, search and user posts
- [linkedin-scraper](https://github.com/toolzerhub/linkedin-scraper): public LinkedIn jobs, companies, profiles and posts
- [google-maps-scraper](https://github.com/toolzerhub/google-maps-scraper): public Google Maps places, details and reviews
- [zillow-scraper](https://github.com/toolzerhub/zillow-scraper): public Zillow listings, property details, Zestimates and price history

## Legal and responsible use

This project is for education and for collecting **publicly available** data. You are responsible for how you use it.

- **Public data only.** The script reads pages anyone can see without an account. Do not use it to get around logins, paywalls, CAPTCHAs or other access controls.
- **Terms and robots rules.** Meta's terms of service may restrict automated access. Read them and decide for yourself; following them is your responsibility.
- **Personal data.** Ads and advertiser pages can contain personal data. Laws such as the GDPR (EU and UK) and the CCPA (California) may apply. Collect only what you need, have a lawful basis, keep it secure, delete it when you no longer need it, and respect people's requests to access or erase their data.
- **Copyright.** Ad images, videos and text belong to their creators. Do not republish them without permission.
- **Be gentle.** Keep request rates low and do not disrupt the service.
- **No warranty.** The software is provided "as is" under the MIT License, without warranty of any kind. The authors are not liable for any claim or damage arising from its use.
- **Not affiliated.** This project is not affiliated with, endorsed by or sponsored by Meta Platforms, Inc. Facebook, Instagram and Meta are trademarks of Meta Platforms, Inc.
- **Takedown requests.** If you own rights in something here and want it changed or removed, email contact@toolzerhub.com.

This section is not legal advice. If you are unsure, talk to a lawyer.

## License

[MIT](LICENSE) © ToolzerHub
