#!/usr/bin/python
# coding: utf-8

import xbmc, xbmcaddon
import json
import datetime
import simplecache
from astral import LocationInfo
from astral.sun import sun

try:
   import zoneinfo
except ImportError:
   from backports import zoneinfo

addon = xbmcaddon.Addon()
addonName = addon.getAddonInfo("name")
addonId = addon.getAddonInfo("id")
addonVersion = addon.getAddonInfo("version")

cache = simplecache.SimpleCache()

INFO = xbmc.LOGINFO
WARNING = xbmc.LOGWARNING
DEBUG = xbmc.LOGDEBUG
ERROR = xbmc.LOGERROR

def log(txt,loglevel=DEBUG,force=False):
   if (addon.getSettingBool('debug') or force) and loglevel not in [WARNING, ERROR]:
      loglevel = INFO
   message = u'[%s] %s' % (addonId, txt)
   xbmc.log(msg=message, level=loglevel)

def getJsonRPC(data):
   try:
      result = json.loads(xbmc.executeJSONRPC(json.dumps(data)))
      return result
   except:
      return

def setJsonRPC(data):
   try:
      xbmc.executeJSONRPC(json.dumps(data))
   except:
      pass

def _safe_cache_get(cachename):
   """Reads the cache while absorbing deserialization errors (eval).

   simplecache uses eval() internally. Old entries containing
   non-primitive objects (ZoneInfo, tzinfo, LocationInfo...) can
   raise NameError. We treat them as a cache miss and delete them.
   """
   try:
      return cache.get(cachename)
   except Exception as e:
      log("Cache stale entry ignored (%s): %s" % (cachename, e), WARNING)
      return None

def suntimes(location, latitude, longitude, timezone=None):
   """Calculates sunrise and sunset times for a given location.

   Args:
      location:  City name (used as cache key)
      latitude:  Latitude of the location
      longitude: Longitude of the location
      timezone:  IANA timezone of the city, e.g. 'Europe/Paris'
                 (optional -- uses system timezone if absent)

   Returns:
      dict with keys 'start', 'end', 'local_timezone' (str),
      'zonecache' and 'timecache'.

   Cache note: only primitive types (str, bool) are stored to
   remain compatible with simplecache's internal eval().
   """
   zonecache = False
   tz_str = None  # timezone as string (for cache and logs)

   if timezone:
      # Timezone provided directly by the geocoder
      try:
         local_timezone = zoneinfo.ZoneInfo(timezone)
         tz_str = timezone
         log("Using city timezone: %s" % tz_str)
      except Exception:
         log("Invalid timezone '%s', falling back to system timezone" % timezone, WARNING)
         local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
         tz_str = str(local_timezone)
   else:
      # Read timezone from cache (stored as string since this fix)
      tz_cachename = addonId + ".timezone"
      cached_tz = _safe_cache_get(tz_cachename)
      if cached_tz and isinstance(cached_tz, str):
         zonecache = True
         tz_str = cached_tz
         try:
            local_timezone = zoneinfo.ZoneInfo(tz_str)
         except Exception:
            local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
            tz_str = str(local_timezone)
      else:
         # Empty cache or old non-string entry: recalculate and re-store
         local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
         tz_str = str(local_timezone)
         cache.set(tz_cachename, tz_str, expiration=datetime.timedelta(hours=12))

   # Read sunrise/sunset cache (contains only 'start' and 'end', str types)
   sun_cachename = addonId + "." + str(location)
   cachedata = _safe_cache_get(sun_cachename)
   if cachedata and isinstance(cachedata, dict) and "start" in cachedata and "end" in cachedata:
      start = cachedata["start"]
      end = cachedata["end"]
      times = {"start": start, "end": end, "local_timezone": tz_str,
               "zonecache": zonecache, "timecache": True}
   else:
      city = LocationInfo(latitude=latitude, longitude=longitude)
      sundata = sun(city.observer, tzinfo=local_timezone)
      start = sundata["sunrise"].strftime("%H:%M:%S")
      end = sundata["sunset"].strftime("%H:%M:%S")
      times = {"start": start, "end": end, "local_timezone": tz_str,
               "zonecache": zonecache, "timecache": False}
      # Stocker uniquement des types primitifs (str) pour eviter le NameError avec eval()
      cache.set(sun_cachename, {"start": start, "end": end},
                expiration=datetime.timedelta(hours=12))
   return times
