#!/usr/bin/python
# coding: utf-8

import xbmc, xbmcaddon, xbmcvfs
import datetime
from resources.lib.utils import *
#import xml.etree.ElementTree as ET
from functools import lru_cache, wraps
from time import monotonic_ns

addon = xbmcaddon.Addon()
addonVersion = addon.getAddonInfo("version")

def timed_lru_cache(_func=None, *, seconds: int = 600, maxsize: int = 128, typed: bool = False):
   def wrapper_cache(f):
      f = lru_cache(maxsize=maxsize, typed=typed)(f)
      f.delta = seconds * 10 ** 9
      f.expiration = monotonic_ns() + f.delta
      @wraps(f)
      def wrapped_f(*args, **kwargs):
         if monotonic_ns() >= f.expiration:
            f.cache_clear()
            f.expiration = monotonic_ns() + f.delta
         return f(*args, **kwargs)
      wrapped_f.cache_info = f.cache_info
      wrapped_f.cache_clear = f.cache_clear
      return wrapped_f
   if _func is None:
      return wrapper_cache
   else:
      return wrapper_cache(_func)

def dialogcheck():
   try:
      dialogcheck = getJsonRPC({"jsonrpc": "2.0","method": "GUI.GetProperties","params": {"properties": ["currentwindow"]},"id": 1})
      windowid = dialogcheck['result']['currentwindow']['id']
      windowname = dialogcheck['result']['currentwindow']['label']
   except:
     windowid = False
     windowname = False
   log("ActiveWindowID: %s (%s)" % (windowid, windowname))
   return windowid,windowname

def playercheck():
   # If "Allow Theme change while playing media" is TRUE, we return False (don't block)
   # If it is FALSE, we return True if something is playing (block)
   if addon.getSettingBool("player"):
      playcheck = False
   else:
      playcheck = xbmc.Player().isPlaying()
      if playcheck:
         # If playing, check if it's paused
         try:
            pausecheck = getJsonRPC({"jsonrpc": "2.0","method": "Player.GetProperties","params": { "playerid": 1, "properties": ["speed"] },"id": 1})
            speedstate = pausecheck['result']['speed']
            if speedstate == 0:
               playcheck = False
         except:
            pass
   log("Player Check (blocking): %s" % playcheck)
   return playcheck

def screensavercheck():
   # If "Allow Theme change when Screensaver is on" is TRUE, we return False (don't block)
   # If it is FALSE, we return the actual screensaver state (block if active)
   if addon.getSettingBool("saver"):
      screensaver = False
   else:
      try:
         savercheck = getJsonRPC({"jsonrpc": "2.0", "method": "XBMC.GetInfoBooleans", "params": { "booleans": ["System.ScreenSaverActive"] }, "id": 1})
         screensaver = savercheck['result']['System.ScreenSaverActive']
      except:
         screensaver = False
   log("Screensaver Check (blocking): %s" % screensaver)
   return screensaver

@timed_lru_cache(seconds=20)
def GetSkinSetting(activeskin):
   autocolor = False
   try:
      with open(xbmcvfs.translatePath(xbmcaddon.Addon(activeskin).getAddonInfo("profile")) + "settings.xml", 'r') as fp:
         for l_no, line in enumerate(fp):
            if 'daynight.autocolor' in line:
               if 'true' in line:
                  autocolor = True
               break
   except:
      autocolor = False
   return autocolor

def main():
   # Get active skin name
   activeskin = xbmc.getSkinDir()
   log("Active Skin: %s" % activeskin)
   if not activeskin == "skin.arctic.zephyr.rounded":
      log("Current active Skin is not Supportet by this Addon!")
      return

   # Reading skin setting: is autocolor enabled
   # --------------------------------------------
   # Its not working??? Kodi20 Returns Nothing!!! Kodi19 Crashed!!!
   #autocolor = xbmcaddon.Addon(activeskin).getSetting("daynight.autocolor")
   # --------------------------------------------
   # And this crashed Kodi with Python = 3.11 and higher
   #SkinPath = xbmcvfs.translatePath(xbmcaddon.Addon(activeskin).getAddonInfo("profile"))
   #tree = ET.parse(SkinPath + "settings.xml")
   #root = tree.getroot()
   #autocolor = root.find('.//setting[@id="daynight.autocolor"]').text
   # --------------------------------------------
   # This is a workaround. Works with Kodi19 and 20
   autocolor = GetSkinSetting(activeskin)
   log("Autocolor enabled: %s" % autocolor)
   if not autocolor:
      return

   # Dont switch when yes/no Dialog is open [id:10100] or Addon Browser [id:10040]
   windowid, windowname = dialogcheck()
   if windowid == 10100 or windowid == 10040:
      return

   #Check if Player is running, stopped or paused
   playcheck = playercheck()
   if playcheck:
      return

   #Check if Screensaver is active
   screensaver = screensavercheck()
   if screensaver:
      return

   # Get current active Color Theme
   try:
      colortheme = getJsonRPC({"jsonrpc": "2.0", "method": "Settings.GetSettingValue", "params": {"setting": "lookandfeel.skincolors"}, "id": 1})
      activecolor = colortheme['result']['value']
   except:
      activecolor = False
   log("Current Theme Color: %s" % activecolor)

   # Calculate Sunrise -> Sunset
   sunchange = addon.getSettingBool("sunchange")
   if sunchange:
      location = addon.getSetting("location")
      latitude = addon.getSetting("latitude")
      longitude = addon.getSetting("longitude")
      times = suntimes(location,latitude,longitude)
      if not times["timecache"]:
         addon.setSetting("start_time_sun", times["start"])
         addon.setSetting("end_time_sun", times["end"])
   else:
      start = addon.getSetting("start_time")
      end = addon.getSetting("end_time")
      times = {"start": start, "end": end, "local_timezone": False, "zonecache": False, "timecache": False}

   # Timeframe for Light Theme Color
   log("Light Theme Timeframe: %s -> %s (Timezone: %s) [Zonecache: %s, Timecache: %s]" % (times["start"], times["end"], times["local_timezone"], times["zonecache"], times["timecache"]))

   # Check timeframe and switch Theme Color
   current_time = datetime.datetime.now().strftime("%H:%M:%S")
   if current_time > times["start"] and current_time < times["end"]:
      # Set Light Theme
      light = addon.getSetting("lightmode")
      if activecolor != light:
         log("Setting Theme Color: %s" % light, force=True)
         setJsonRPC({"jsonrpc": "2.0","method": "Settings.SetSettingValue","id": 1,"params": {"setting": "lookandfeel.skincolors","value": light}})
   else:
      # Set Dark Theme
      dark = addon.getSetting("darkmode")
      if activecolor != dark:
         log("Setting Theme Color: %s" % dark, force=True)
         setJsonRPC({"jsonrpc": "2.0","method": "Settings.SetSettingValue","id": 1,"params": {"setting": "lookandfeel.skincolors","value": dark}})


if __name__ == '__main__':
   log("Version %s is started" % addonVersion, force=True)
   main()
   monitor = xbmc.Monitor()
   while not monitor.abortRequested():
      monitor.waitForAbort(5)
      main()
   log("Version %s is stopped" % addonVersion, force=True)
