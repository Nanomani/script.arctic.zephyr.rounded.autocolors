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
   """Lit le cache en absorbant les erreurs de deserialisation (eval).

   simplecache utilise eval() en interne. Des anciennes entrees contenant
   des objets non-primitifs (ZoneInfo, tzinfo, LocationInfo...) peuvent
   lever NameError. On les traite comme un cache miss et on les supprime.
   """
   try:
      return cache.get(cachename)
   except Exception as e:
      log("Cache stale entry ignored (%s): %s" % (cachename, e), WARNING)
      return None

def suntimes(location, latitude, longitude, timezone=None):
   """Calcule les heures de lever et coucher du soleil pour un lieu donne.

   Args:
      location:  Nom de la ville (utilise comme cle de cache)
      latitude:  Latitude du lieu
      longitude: Longitude du lieu
      timezone:  Fuseau horaire IANA de la ville, ex. 'Europe/Paris'
                 (optionnel -- utilise le timezone systeme si absent)

   Returns:
      dict avec les cles 'start', 'end', 'local_timezone' (str),
      'zonecache' et 'timecache'.

   Note cache: seuls des types primitifs (str, bool) sont stockes pour
   rester compatibles avec le eval() interne de simplecache.
   """
   zonecache = False
   tz_str = None  # fuseau horaire sous forme de chaine (pour cache et logs)

   if timezone:
      # Fuseau horaire fourni directement par le geocoder
      try:
         local_timezone = zoneinfo.ZoneInfo(timezone)
         tz_str = timezone
         log("Using city timezone: %s" % tz_str)
      except Exception:
         log("Invalid timezone '%s', falling back to system timezone" % timezone, WARNING)
         local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
         tz_str = str(local_timezone)
   else:
      # Lire le timezone depuis le cache (stocke comme chaine depuis ce correctif)
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
         # Cache vide ou ancienne entree non-string : recalculer et re-stocker
         local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
         tz_str = str(local_timezone)
         cache.set(tz_cachename, tz_str, expiration=datetime.timedelta(hours=12))

   # Lire le cache lever/coucher (ne contient que 'start' et 'end', types str)
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
