"""Scrape the public Meta (Facebook) Ad Library with Python. No login, no API token, one file."""
import argparse
import csv
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from itertools import islice
from urllib.parse import parse_qs, quote, urlencode, urlparse

from curl_cffi import requests

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
LIBRARY_URL = "https://www.facebook.com/ads/library/"
# The Ad Library web app names each GraphQL query by a doc_id. They change every
# few months; when a command starts failing, grab the new id from the web app.
DOC_SEARCH = "24922295957467452"  # AdLibrarySearchPaginationQuery (keyword and page search)
DOC_DETAILS = "25068828942793558"  # AdLibraryV3AdDetailsQuery
DOC_TYPEAHEAD = "9755915494515334"  # useAdLibraryTypeaheadSuggestionDataSourceQuery
PAGE_SIZE = 10  # Meta returns at most 10 ads per request, whatever you ask for
RATE_LIMIT_CODE = 1675004
DELEGATE_PAGE = re.compile(r'"delegate_page"\s*:\s*\{\s*"id"\s*:\s*"(\d+)"')

CSV_COLUMNS = [
    "ad_archive_id", "ad_url", "page_id", "page_name", "page_url", "is_active", "start_date", "end_date",
    "platforms", "countries", "ad_text", "title", "cta_text", "link_url", "display_format", "media_type",
    "image_urls", "video_hd_urls", "video_sd_urls", "impressions", "spend_min", "spend_max", "currency",
]


class ScrapeError(Exception):
    pass


def iso(ts):
    return datetime.fromtimestamp(int(ts), timezone.utc).isoformat() if ts else None


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bounds(value):
    """Meta gives spend and reach as {lower_bound, upper_bound}, or as text like '$40K - $45K' or '>1M'."""
    if isinstance(value, dict):
        return to_int(value.get("lower_bound")), to_int(value.get("upper_bound"))
    if not isinstance(value, str):
        return None, None
    nums = [float(n) * {"K": 1e3, "M": 1e6, "": 1}[u.upper()] for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*([KkMm]?)", value)]
    nums = [int(n) for n in nums]
    if value.strip().startswith(">") and nums:
        return nums[0], None
    if value.strip().startswith("<") and nums:
        return None, nums[0]
    return (nums[0], nums[-1]) if nums else (None, None)


def uniq(items):
    return list(dict.fromkeys(i for i in items if i))


def ad_url(ad_id):
    return f"{LIBRARY_URL}?id={ad_id}"


class AdLibrary:
    """A logged-out session. Meta hands out its guest `datr` cookie on the first reply."""

    def __init__(self, proxy=None):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        self.http = requests.Session(impersonate="chrome", proxies=proxies)
        self.http.cookies.update({"ps_l": "1", "ps_n": "1", "wd": "1920x1080"})
        self.session_id = str(uuid.uuid4())

    def _request(self, method, url, **kwargs):
        try:
            resp = self.http.request(method, url, timeout=60, allow_redirects=False, **kwargs)
        except requests.RequestsError as exc:
            raise ScrapeError(f"Network error: {exc}") from exc
        if resp.status_code in (301, 302, 401, 403, 429):
            raise ScrapeError(
                f"Facebook answered HTTP {resp.status_code}: blocked or rate-limited. "
                "Cloud and datacenter IPs are blocked most; try a home connection or --proxy."
            )
        if resp.status_code == 404:
            raise ScrapeError("Not found.")
        if resp.status_code != 200:
            raise ScrapeError(f"Unexpected HTTP {resp.status_code} from Facebook.")
        return resp

    def graphql(self, name, doc_id, variables):
        body = {
            "av": "0", "__user": "0", "__a": "1", "__req": "1", "dpr": "1", "__ccg": "MODERATE",
            "fb_api_caller_class": "RelayModern", "fb_api_req_friendly_name": name,
            "server_timestamps": "true", "doc_id": doc_id,
            "variables": json.dumps(variables, separators=(",", ":")),
        }
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "x-fb-friendly-name": name,
            "x-asbd-id": "359341",
            "referer": LIBRARY_URL,
        }
        text = self._request("POST", GRAPHQL_URL, data=urlencode(body), headers=headers).text
        text = text.removeprefix("for (;;);")
        try:
            data = json.loads(text)
        except ValueError:
            raise ScrapeError("Facebook sent a page instead of data: blocked. Try a home connection or --proxy.")
        errors = data.get("errors") or []
        if any(e.get("code") == RATE_LIMIT_CODE for e in errors) or re.search(r"rate.limit|too.many.requests", str(errors), re.I):
            raise ScrapeError("Facebook rate-limited or blocked this IP. Cloud and datacenter IPs are hit most: use a home connection or --proxy, or wait a few minutes.")
        main = (data.get("data") or {}).get("ad_library_main")
        if not main:
            raise ScrapeError(f"Facebook returned no data for {name}: {str(errors)[:200]}")
        return main

    # --- ads -------------------------------------------------------------

    def iter_ads(self, search_type, country="US", status="active", query="", page_id="0", media="all",
                 platforms=(), date_min=None, date_max=None):
        """Yield ads one by one, following Meta's cursor until the results run out."""
        seen, cursor = set(), None
        while True:
            variables = {
                "activeStatus": status, "adType": "ALL", "bylines": [], "collationToken": None,
                "contentLanguages": [], "countries": [country], "cursor": cursor, "excludedIDs": None,
                "first": PAGE_SIZE, "isTargetedCountry": False, "location": None, "mediaType": media,
                "multiCountryFilterMode": None, "pageIDs": [], "potentialReachInput": None,
                "publisherPlatforms": list(platforms), "queryString": query, "regions": None,
                "searchType": search_type, "sessionID": self.session_id, "sortData": None,
                "startDate": {"min": date_min or "", "max": date_max or ""} if date_min or date_max else None,
                "source": None, "v": "ab23c0", "viewAllPageID": page_id,
            }
            conn = self.graphql("AdLibrarySearchPaginationQuery", DOC_SEARCH, variables).get("search_results_connection")
            if conn is None:
                raise ScrapeError("Facebook returned no search results for this request.")
            for edge in conn.get("edges") or []:
                for item in (edge.get("node") or {}).get("collated_results") or []:
                    if item.get("ad_archive_id") and item["ad_archive_id"] not in seen:
                        seen.add(item["ad_archive_id"])
                        yield clean_ad(item)
            info = conn.get("page_info") or {}
            cursor = info.get("end_cursor")
            if not info.get("has_next_page") or not cursor:
                return
            time.sleep(0.5)

    def ads(self, search_type, limit, **filters):
        return list(islice(self.iter_ads(search_type, **filters), limit))

    def search(self, keyword, exact=False, **filters):
        return self.ads("KEYWORD_EXACT_PHRASE" if exact else "KEYWORD_UNORDERED", query=keyword, **filters)

    def page_ads(self, page, **filters):
        return self.ads("PAGE", page_id=self.page_id(page), **filters)

    # --- pages -----------------------------------------------------------

    def page_id(self, value):
        """Turn a numeric id, an Ad Library link, a Facebook page URL or a username into the numeric page id."""
        value = value.strip().lstrip("@")
        if re.fullmatch(r"\d{3,}", value):
            return value
        slug = value
        if re.match(r"https?://", value):
            url = urlparse(value)
            query = parse_qs(url.query)
            found = (query.get("view_all_page_id") or query.get("id") or [""])[0]
            if url.path.startswith(("/ads/library", "/profile.php")) and re.fullmatch(r"\d{3,}", found):
                return found
            parts = [p for p in url.path.split("/") if p]
            slug = parts[0] if parts else ""
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", slug):
            raise ScrapeError(f"Not a page id, page URL or username: {value}")
        # The page's HTML carries the numeric id the Ad Library uses.
        html = self._request("GET", f"https://www.facebook.com/{quote(slug)}/", headers={
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "sec-fetch-dest": "document", "sec-fetch-mode": "navigate", "sec-fetch-site": "none",
            "upgrade-insecure-requests": "1",
        }).text
        m = DELEGATE_PAGE.search(html)
        if not m:
            raise ScrapeError(f"Could not find a page id for {value}. Check the username, or pass the numeric page id (find it with the pages command).")
        return m.group(1)

    def pages(self, name, country="US", limit=10):
        """Advertiser pages that match a name, from the Ad Library's own search box."""
        variables = {"queryString": name, "isMobile": False, "country": country, "adType": "ALL"}
        data = self.graphql("useAdLibraryTypeaheadSuggestionDataSourceQuery", DOC_TYPEAHEAD, variables)
        results = (data.get("typeahead_suggestions") or {}).get("page_results") or []
        return [{
            "page_id": r.get("page_id"),
            "name": r.get("name"),
            "url": f"https://www.facebook.com/{r.get('page_alias') or r.get('page_id')}/",
            "alias": r.get("page_alias"),
            "category": r.get("category"),
            "likes": r.get("likes"),
            "is_verified": r.get("verification") == "BLUE_VERIFIED",
            "instagram_username": r.get("ig_username"),
            "instagram_followers": r.get("ig_followers"),
            "is_deleted": r.get("page_is_deleted"),
            "image_url": r.get("image_uri"),
        } for r in results[:limit]]

    # --- one ad ----------------------------------------------------------

    def ad(self, ad_id, page, country="US", scan=30):
        """One ad: its creative, found in the advertiser's ads, plus Meta's detail record for it."""
        page_id = self.page_id(page)
        ad = next((a for a in islice(self.iter_ads("PAGE", country=country, status="all", page_id=page_id), scan * PAGE_SIZE)
                   if a["ad_archive_id"] == ad_id), None)
        if not ad:
            raise ScrapeError(f"Ad {ad_id} not found in the first {scan * PAGE_SIZE} ads of page {page_id} in {country}. "
                              "Check the id and page, try --country ALL, or raise --scan.")
        variables = {
            "adArchiveID": ad_id, "pageID": page_id, "country": country, "sessionID": self.session_id,
            "source": None, "isAdNonPolitical": False, "isAdNotAAAEligible": False,
        }
        d = self.graphql("AdLibraryV3AdDetailsQuery", DOC_DETAILS, variables).get("ad_details") or {}
        adv = d.get("advertiser") or {}
        info = (adv.get("ad_library_page_info") or {}).get("page_info") or {}
        spend = (adv.get("ad_library_page_info") or {}).get("page_spend") or {}
        eu = (d.get("transparency_by_location") or {}).get("eu_transparency") or {}
        insights = d.get("insights") or {}
        # Audience numbers exist only for ads Meta must disclose (political, issue and EU/UK ads).
        ad["details"] = {
            "page_about": ((adv.get("page") or {}).get("about") or {}).get("text") or None,
            "page_category": info.get("page_category"),
            "page_is_verified": info.get("page_verification") == "BLUE_VERIFIED",
            "instagram_username": info.get("ig_username"),
            "instagram_followers": info.get("ig_followers"),
            "is_taken_down": (d.get("aaa_info") or {}).get("is_ad_taken_down"),
            "violation_types": d.get("violation_types") or [],
            "audience_country": insights.get("single_country"),
            "audience_age_gender": insights.get("age_gender_data") or [],
            "audience_regions": sorted((r for r in insights.get("location_data") or [] if r.get("reach")), key=lambda r: -r["reach"]),
            "eu_total_reach": eu.get("eu_total_reach"),
            "eu_age_country_gender": eu.get("age_country_gender_reach_breakdown") or [],
            "page_lifetime_spend": spend.get("lifetime_by_disclaimer") or [],
        }
        return ad

    # --- media -----------------------------------------------------------

    def download(self, ads, folder):
        """Save each ad's videos (HD when there is one) and images into `folder`."""
        os.makedirs(folder, exist_ok=True)
        for ad in ads:
            urls = [v["hd_url"] or v["sd_url"] for v in ad["videos"]] + ad["image_urls"]
            ad["downloaded"] = []
            for n, url in enumerate(uniq(urls), 1):
                ext = os.path.splitext(urlparse(url).path)[1].lower() or ".bin"
                path = os.path.join(folder, f"{ad['ad_archive_id']}_{n}{ext}")
                if not os.path.exists(path):
                    try:
                        data = self._request("GET", url).content
                    except ScrapeError as exc:
                        print(f"Skipped {path}: {exc}", file=sys.stderr)
                        continue
                    with open(path, "wb") as f:
                        f.write(data)
                ad["downloaded"].append(path)
            print(f"{ad['ad_archive_id']}: {len(ad['downloaded'])} file(s) saved", file=sys.stderr)


def clean_ad(item):
    snap = item.get("snapshot") or {}
    cards = snap.get("cards") or []
    # Meta puts media in one of three lists: `videos`, `images`, or `cards` (carousels and catalog ads).
    video_cards = [c for c in cards if c.get("video_hd_url") or c.get("video_sd_url")]
    videos = [
        {"hd_url": v.get("video_hd_url") or None, "sd_url": v.get("video_sd_url") or None,
         "preview_url": v.get("video_preview_image_url") or None}
        for v in (snap.get("videos") or []) + video_cards
    ]
    videos = list({(v["hd_url"], v["sd_url"]): v for v in videos}.values())  # cards often repeat one video
    images = [i.get("original_image_url") or i.get("resized_image_url") for i in snap.get("images") or []]
    images += [c.get("original_image_url") or c.get("resized_image_url") for c in cards if c not in video_cards]
    images = uniq(images)
    if videos:
        media_type = "video"
    elif len(images) > 1:
        media_type = "carousel"
    else:
        media_type = "image" if images else "none"
    spend_min, spend_max = bounds(item.get("spend"))
    reach_min, reach_max = bounds(item.get("reach_estimate"))
    return {
        "ad_archive_id": item["ad_archive_id"],
        "ad_url": ad_url(item["ad_archive_id"]),
        "page_id": item.get("page_id") or snap.get("page_id"),
        "page_name": snap.get("page_name") or item.get("page_name"),
        "page_url": snap.get("page_profile_uri"),
        "page_likes": snap.get("page_like_count"),
        "page_categories": snap.get("page_categories") or [],
        "is_active": item.get("is_active"),
        "start_date": iso(item.get("start_date")),
        "end_date": iso(item.get("end_date")),
        "platforms": item.get("publisher_platform") or [],
        "countries": item.get("targeted_or_reached_countries") or [],
        "ad_text": (snap.get("body") or {}).get("text"),
        "title": snap.get("title"),
        "link_description": snap.get("link_description"),
        "cta_text": snap.get("cta_text"),
        "cta_type": snap.get("cta_type"),
        "link_url": snap.get("link_url"),
        "display_format": snap.get("display_format"),
        "media_type": media_type,
        "image_urls": images,
        "videos": videos,
        "cards": [
            {"title": c.get("title"), "text": c.get("body"), "link_url": c.get("link_url"), "cta_text": c.get("cta_text")}
            for c in cards
        ],
        "variants": item.get("collation_count") or 1,
        "impressions": (item.get("impressions_with_index") or {}).get("impressions_text"),
        "spend_min": spend_min,
        "spend_max": spend_max,
        "currency": item.get("currency") or None,
        "reach_min": reach_min,
        "reach_max": reach_max,
    }


def write_csv(ads, stream):
    """One row per ad. Lists are joined with ' | '; the full detail stays in the JSON."""
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for ad in ads:
        row = dict(ad)
        row["video_hd_urls"] = [v["hd_url"] for v in ad["videos"] if v["hd_url"]]
        row["video_sd_urls"] = [v["sd_url"] for v in ad["videos"] if v["sd_url"]]
        writer.writerow({k: " | ".join(map(str, v)) if isinstance(v, list) else v for k, v in row.items()})


def library_id(value):
    """Accept an ad archive id or an Ad Library link that carries `id=`."""
    value = value.strip()
    if value.isdigit():
        return value, None
    query = parse_qs(urlparse(value).query)
    found = (query.get("id") or [""])[0]
    if not found.isdigit():
        raise ScrapeError(f"Not an ad archive id or Ad Library link: {value}")
    return found, (query.get("view_all_page_id") or [None])[0]


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--proxy", default=os.environ.get("HTTPS_PROXY"), help="proxy URL, e.g. http://user:pass@host:port")
    common.add_argument("-o", "--output", help="write the result to this file")
    ads_args = argparse.ArgumentParser(add_help=False)
    ads_args.add_argument("--country", default="US", help="two-letter country code, or ALL (default US)")
    state = ads_args.add_mutually_exclusive_group()
    state.add_argument("--active", dest="status", action="store_const", const="active", help="only ads running now (default)")
    state.add_argument("--all", dest="status", action="store_const", const="all", help="running and ended ads")
    ads_args.add_argument("--media", choices=["all", "image", "video", "meme"], default="all")
    ads_args.add_argument("--platform", action="append", choices=["FACEBOOK", "INSTAGRAM", "AUDIENCE_NETWORK", "MESSENGER", "THREADS"],
                          help="only ads shown on this platform (repeatable)")
    ads_args.add_argument("--date-min", help="ads that started on or after YYYY-MM-DD")
    ads_args.add_argument("--date-max", help="ads that started on or before YYYY-MM-DD")
    ads_args.add_argument("--limit", type=int, default=20, help="how many ads to return (default 20)")
    ads_args.add_argument("--csv", action="store_true", help="write CSV instead of JSON")
    ads_args.add_argument("--download", metavar="DIR", help="save the ad videos and images into this folder")
    ads_args.set_defaults(status="active")

    parser = argparse.ArgumentParser(description="Scrape the public Meta Ad Library. No login, no API token.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("search", parents=[common, ads_args], help="ads that match a keyword")
    p.add_argument("keyword")
    p.add_argument("--exact", action="store_true", help="match the exact phrase")
    p = sub.add_parser("page", parents=[common, ads_args], help="all ads of one advertiser")
    p.add_argument("page", help="page id, Facebook page URL, Ad Library link or username")
    p = sub.add_parser("pages", parents=[common], help="find advertiser pages by name")
    p.add_argument("name")
    p.add_argument("--country", default="US")
    p.add_argument("--limit", type=int, default=10, help="how many pages to return (default 10)")
    p = sub.add_parser("ad", parents=[common], help="one ad with its details")
    p.add_argument("ad", help="ad archive id or Ad Library link")
    p.add_argument("--page", help="the advertiser page (id, URL or username); not needed if the link has view_all_page_id")
    p.add_argument("--country", default="US", help="two-letter country code, or ALL (default US)")
    p.add_argument("--scan", type=int, default=30, help="how many pages of 10 ads to search for the ad (default 30)")
    p.add_argument("--download", metavar="DIR", help="save the ad videos and images into this folder")
    args = parser.parse_args()

    try:
        lib = AdLibrary(args.proxy)
        if args.command in ("search", "page"):
            if args.limit < 1:
                raise ScrapeError("--limit must be 1 or more.")
            filters = dict(limit=args.limit, country=args.country.upper(), status=args.status, media=args.media,
                           platforms=args.platform or [], date_min=args.date_min, date_max=args.date_max)
            data = lib.search(args.keyword, exact=args.exact, **filters) if args.command == "search" else lib.page_ads(args.page, **filters)
            if args.download:
                lib.download(data, args.download)
        elif args.command == "pages":
            data = lib.pages(args.name, args.country.upper(), args.limit)
        else:
            ad_id, link_page = library_id(args.ad)
            page = args.page or link_page
            if not page:
                raise ScrapeError("Meta needs the advertiser page for one ad. Pass --page (id, URL or username), "
                                  "or use a link that has view_all_page_id. Find the page with: pages <name>")
            data = lib.ad(ad_id, page, args.country.upper(), args.scan)
            if args.download:
                lib.download([data], args.download)
    except ScrapeError as exc:
        sys.exit(f"Error: {exc}")

    if isinstance(data, list) and not data:
        print("No results. Try --all (also ended ads), another --country, or a different search.", file=sys.stderr)
    out = open(args.output, "w", encoding="utf-8", newline="") if args.output else sys.stdout
    if getattr(args, "csv", False):
        write_csv(data, out)
    else:
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if args.output:
        out.close()
        print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
