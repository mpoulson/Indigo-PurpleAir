#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import indigo
import os
import sys
import traceback
import random
import re
import time
from datetime import datetime,tzinfo,timedelta

from PurpleAir import PurpleAir

from copy import deepcopy
from ghpu import GitHubPluginUpdater

try:
	import simplejson as json
except:
	import json

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		self.debug = pluginPrefs.get("debug", False)
		self.PurpleAir = PurpleAir(self)
		self.retryCount = 0
		self.keepProcessing = True
		self.restartCount = 0

	def _refreshStatesFromHardware(self, dev):
		self.debugLog(u"Getting data for Sensor : %s" % dev.address)
		data = PurpleAir.GetData(self.PurpleAir,dev.address)

		#TODO Add logic to not post when no changes
		self.updateStateOnServer(dev,"currentTemp", data.currentTemp)
		self.updateStateOnServer(dev,"uptime", data.uptime)
		self.updateStateOnServer(dev,"version", data.version)
		self.updateStateOnServer(dev,"hardwarediscovered", data.hardwarediscovered)
		self.updateStateOnServer(dev,"hardwareversion", data.hardwareversion)
		self.updateStateOnServer(dev,"name", data.geo)
		self.updateStateOnServer(dev,"lat", data.lat)
		self.updateStateOnServer(dev,"lon", data.lon)
		self.updateStateOnServer(dev,"currentHumidity", data.currentHumidity)
		self.updateStateOnServer(dev,"currentDewPoint", data.currentDewPoint)
		self.updateStateOnServer(dev,"currentPressure", data.currentPressure)
		self.updateStateOnServer(dev,"current25", data.current25)
		self.updateStateOnServer(dev,"current10", data.current10)
		self.updateStateOnServer(dev,"current1", data.current1)

	def updateStateOnServer(self, dev, state, value):
		if dev.states[state] != value:
			self.debugLog(u"Updating Device: %s, State: %s, Value: %s" % (dev.name, state, value))
			dev.updateStateOnServer(state, value)
			
	# ########################################
	def startup(self):
		self.debug = self.pluginPrefs.get('showDebugInLog', False)
		self.debugLog(u"startup called")

		self.updater = GitHubPluginUpdater(self)
		#self.updater.checkForUpdate()
		self.updateFrequency = float(self.pluginPrefs.get('updateFrequency', 24)) * 60.0 * 60.0
		self.debugLog(u"updateFrequency = " + str(self.updateFrequency))
		self.next_update_check = time.time()

	def shutdown(self):
		self.keepProcessing = False
		self.debugLog(u"shutdown called")

	# ########################################
	def runConcurrentThread(self):
		try:
			while self.keepProcessing:
				indigo.server.log(u"Processing...")
				if (self.updateFrequency > 0.0) and (time.time() > self.next_update_check):
					self.next_update_check = time.time() + self.updateFrequency
					self.updater.checkForUpdate()

				for dev in indigo.devices.iter("self"):
					if not dev.enabled:
						continue
					if (int(self.pluginPrefs.get("maxRetry", 5)) != 0 and self.retryCount >= int(self.pluginPrefs.get("maxRetry", 5))):
						self.errorLog("Reached max retry attempts.  Won't Refresh from Server. !")
						self.sleep(36000)

					self._refreshStatesFromHardware(dev)
					self.restartCount = self.restartCount + 1

				if (self.restartCount > 10000):
					self.restartCount = 0
					indigo.server.log(u"Memory Leak Prevention. Restarting Plugin. - This will happen until I find and fix the leak")
					serverPlugin = indigo.server.getPlugin(self.pluginId)
					serverPlugin.restart(waitUntilDone=False)
					break

				self.sleep(int(self.pluginPrefs.get("refreshInterval",30)))
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.

	# ########################################
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		indigo.server.log(u"validateDeviceConfigUi \"%s\"" % (valuesDict))
		return (True, valuesDict)

	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u"Vaidating Plugin Configuration")
		errorsDict = indigo.Dict()
		if valuesDict[u"refreshInterval"] == "":
			errorsDict[u"refreshInterval"] = u"Please enter refresh value."
		else:
			try: int(valuesDict[u"refreshInterval"])
			except:
				errorsDict[u"maxRetry"] = u"Please enter a valid refresh Value."
		if len(errorsDict) > 0:
			self.errorLog(u"\t Validation Errors")
			return (False, valuesDict, errorsDict)
		else:
			self.debugLog(u"\t Validation Succesful")
			return (True, valuesDict)
		return (True, valuesDict)

	########################################
	def initDevice(self, dev):
		self.debugLog("Initializing PurpleAir device: %s" % dev.name)
		data = PurpleAir.GetData(self.PurpleAir,dev.address)

		self.updateStateOnServer(dev,"currentTemp", data.currentTemp)
		self.updateStateOnServer(dev,"uptime", data.uptime)
		self.updateStateOnServer(dev,"version", data.version)
		self.updateStateOnServer(dev,"hardwarediscovered", data.hardwarediscovered)
		self.updateStateOnServer(dev,"hardwareversion", data.hardwareversion)
		self.updateStateOnServer(dev,"name", data.geo)
		self.updateStateOnServer(dev,"lat", data.lat)
		self.updateStateOnServer(dev,"lon", data.lon)
		self.updateStateOnServer(dev,"currentHumidity", data.currentHumidity)
		self.updateStateOnServer(dev,"currentDewPoint", data.currentDewPoint)
		self.updateStateOnServer(dev,"currentPressure", data.currentPressure)
		self.updateStateOnServer(dev,"current25", data.current25)
		self.updateStateOnServer(dev,"current10", data.current10)
		self.updateStateOnServer(dev,"current1", data.current1)

	def deviceStartComm(self, dev):
		self.initDevice(dev)

		dev.stateListOrDisplayStateIdChanged()
		self.debugLog("Initialize %s" % dev.address)
		
	def deviceStopComm(self, dev):
		# Called when communication with the hardware should be shutdown.
		pass

	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		self.debugLog(u"validateDeviceConfigUi called with valuesDict: %s" % str(valuesDict))
		
		return (True, valuesDict)

	def checkForUpdates(self):
		self.updater.checkForUpdate()

	def updatePlugin(self):
		self.updater.update()

	def forceUpdate(self):
		self.updater.update(currentVersion='0.0.0')
	