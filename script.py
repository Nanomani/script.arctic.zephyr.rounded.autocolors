#!/usr/bin/python
# coding: utf-8

from resources.lib.utils import *
import xbmc, xbmcgui, xbmcaddon
from sys import argv
import simplecache
from astral.geocoder import search_locations
from astral import LocationInfo

addon = xbmcaddon.Addon()
addonName = addon.getAddonInfo("name")

location = addon.getSetting("location")
cache = simplecache.SimpleCache()

# Location search via astral.geocoder.search_locations()
# (previously via Yahoo Weather API which is no longer available)
#
# Note: simplecache uses eval() for deserialization. We therefore store
# results as a list of dicts (primitive types) rather than LocationInfo
# objects, to avoid a NameError during deserialization.
# The try/except on cache.get() absorbs old cache entries that contained
# LocationInfo objects (incompatible format).

def _locs_to_cache(locs):
   """Converts a list of LocationInfo to a list of serializable dicts."""
   return [{"name": l.name, "region": l.region, "timezone": l.timezone,
            "latitude": l.latitude, "longitude": l.longitude} for l in locs]

def _locs_from_cache(data):
   """Reconstructs a list of LocationInfo from cached dicts."""
   return [LocationInfo(name=d["name"], region=d["region"],
                        timezone=d["timezone"], latitude=d["latitude"],
                        longitude=d["longitude"]) for d in data]

def search_location():
   keyboard = xbmc.Keyboard(location, xbmc.getLocalizedString(14024), False)
   keyboard.doModal()
   dialog = xbmcgui.Dialog()
   if (keyboard.isConfirmed() and keyboard.getText()):
      text = keyboard.getText()
      log("Searching for location: %s" % text)

      cachekey = "loc_search_" + text.lower().replace(" ", "_")
      cachedata = None
      try:
         # simplecache calls eval() internally — an old entry in
         # LocationInfo format will raise NameError here; we treat it
         # as a cache miss and replace it with the new dict format.
         cachedata = cache.get(cachekey)
      except Exception as e:
         log("Cache read error (stale entry purged): %s" % e, WARNING)

      if cachedata:
         locs = _locs_from_cache(cachedata)
         usecache = True
      else:
         locs = search_locations(text, count=10)
         if locs:
            cache.set(cachekey, _locs_to_cache(locs))
         usecache = False

      log("Location results: %d found (Cache: %s)" % (len(locs), usecache))

      if locs:
         items = []
         for loc in locs:
            label1 = loc.name
            label2 = loc.name
            if loc.region:
               label2 += " (%s)" % loc.region
            label2 += " - %s  [%.4f / %.4f]" % (loc.timezone, loc.latitude, loc.longitude)
            listitem = xbmcgui.ListItem(label1, label2)
            items.append(listitem)

         selected = dialog.select(xbmc.getLocalizedString(396), items, useDetails=True)
         if selected != -1:
            sel = locs[selected]
            addon.setSetting("location", sel.name)
            addon.setSettingNumber("latitude", sel.latitude)
            addon.setSettingNumber("longitude", sel.longitude)
            # Calculate and save sunrise/sunset with the city's timezone
            times = suntimes(sel.name, sel.latitude, sel.longitude, sel.timezone)
            addon.setSetting("start_time_sun", times["start"])
            addon.setSetting("end_time_sun", times["end"])
            log("Selected location: %s (%s) tz=%s lat=%s lon=%s" % (
               sel.name, sel.region, sel.timezone, sel.latitude, sel.longitude))
      else:
         log("No locations found for: %s" % text, force=True)
         dialog.ok(addonName, xbmc.getLocalizedString(284))

if __name__ == '__main__':
   if len(argv) > 1:
      search_location()
   else:
      addon.openSettings()
