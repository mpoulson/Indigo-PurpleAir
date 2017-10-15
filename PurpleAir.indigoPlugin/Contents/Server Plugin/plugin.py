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
		self.deviceList = {}

	def _refreshStatesFromHardware(self, dev):

		#self.debugLog(u"Getting data for Sensor : %s" % dev)
		if dev.deviceTypeId != "RemotePurpleAirSensor":
			#self.debugLog(u"Getting data for Sensor : %s" % dev.address)
			data = PurpleAir.GetData(self.PurpleAir,dev.address)
		else:
			#self.debugLog(u"Getting data for Remote Sensor : %s with ID %s" % (dev.name,dev.address))
			data = PurpleAir.GetRemoteData(self.PurpleAir,dev.address)

		try: self.updateStateOnServer(dev, "currentTemp", int(data.currentTemp))
		except: self.de (dev, "currentTemp")
		
		try: self.updateStateOnServer(dev, "version", data.version)
		except: self.de (dev, "version")
		try: self.updateStateOnServer(dev, "currentHumidity", int(data.currentHumidity))
		except: self.de (dev, "currentHumidity")
		
		try: self.updateStateOnServer(dev, "currentPressure", str(data.currentPressure))
		except: self.de (dev, "currentPressure")
		try: self.updateStateOnServer(dev, "current25", float(data.current25))
		except: self.de (dev, "current25")
		try: self.updateStateOnServer(dev, "lat", data.lat)
		except: self.de (dev, "lat")
		try: self.updateStateOnServer(dev, "lon", data.lon)
		except: self.de (dev, "lon")

		#The local devices don't have 24hr PM2.5
		if dev.deviceTypeId == "RemotePurpleAirSensor":
			try: self.updateStateOnServer(dev, "AQI", int(data.aqi))
			except: self.de (dev, "AQI")
		else:
			try: self.updateStateOnServer(dev, "current10", float(data.current10))
			except: self.de (dev, "current10")
			try: self.updateStateOnServer(dev, "current1", float(data.current1))
			except: self.de (dev, "current1")
			try: self.updateStateOnServer(dev, "currentDewPoint", float(data.currentDewPoint))
			except: self.de (dev, "currentDewPoint")
			try: self.updateStateOnServer(dev, "uptime", int(data.uptime))
			except: self.de (dev, "uptime")
			try: self.updateStateOnServer(dev, "hardwarediscovered", data.hardwarediscovered)
			except: self.de (dev, "hardwarediscovered")
			try: self.updateStateOnServer(dev, "hardwareversion", data.hardwareversion)
			except: self.de (dev, "hardwareversion")
		#twilioDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)


	def updateStateOnServer(self, dev, state, value):
		# if dev.states[state] != value and (dev.states[state] != "" and value != None):
		# 	self.debugLog(u"Updating Device: %s, State: %s, Value: '%s', From Current Value '%s'" % (dev.name, state, value, dev.states[state]))
		dev.updateStateOnServer(state, value)

	def de (self, dev, value):
		self.errorLog ("[%s] No value found for device: %s, field: %s" % (time.asctime(), dev.name, value))
			
	# ########################################
	def startup(self):
		self.debug = self.pluginPrefs.get('showDebugInLog', False)
		self.debugLog(u"startup called")

		self.updater = GitHubPluginUpdater(self)
		#self.updater.checkForUpdate()
		self.updateFrequency = float(self.pluginPrefs.get('updateFrequency', 24)) * 60.0 * 60.0
		self.debugLog(u"updateFrequency = " + str(self.updateFrequency))
		self.next_update_check = time.time()
		self.buildAvailableDeviceList()

	def shutdown(self):
		self.keepProcessing = False
		self.debugLog(u"shutdown called")

	# ########################################
	def runConcurrentThread(self):
		try:
			while self.keepProcessing:
				#indigo.server.log(u"Processing...")
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
		if dev.deviceTypeId != "RemotePurpleAirSensor":
			self.debugLog("Initializing PurpleAir device: %s" % dev.name)
			data = PurpleAir.GetData(self.PurpleAir,dev.address)
		else:
			self.debugLog("Getting data for remote PurpleAir device: %s" % dev.name)
			data = PurpleAir.GetRemoteData(self.PurpleAir,dev.address)

		self.updateStateOnServer(dev,"currentTemp", data.currentTemp)
		self.updateStateOnServer(dev,"name", data.label)
		self.updateStateOnServer(dev,"lat", data.lat)
		self.updateStateOnServer(dev,"lon", data.lon)
		self.updateStateOnServer(dev,"currentHumidity", data.currentHumidity)
		self.updateStateOnServer(dev,"currentPressure", str(data.currentPressure))
		self.updateStateOnServer(dev,"current25", data.current25)
		if dev.deviceTypeId != "RemotePurpleAirSensor":
			self.updateStateOnServer(dev,"current10", data.current10)
			self.updateStateOnServer(dev,"current1", data.current1)
			self.updateStateOnServer(dev,"uptime", data.uptime)
			self.updateStateOnServer(dev,"version", data.version)
			self.updateStateOnServer(dev,"hardwarediscovered", data.hardwarediscovered)
			self.updateStateOnServer(dev,"hardwareversion", data.hardwareversion)
			self.updateStateOnServer(dev,"currentDewPoint", data.currentDewPoint)

	def buildAvailableDeviceList(self):
		self.debugLog("Building Available Device List")

		self.deviceList = PurpleAir.GetDevices(self.PurpleAir)

		indigo.server.log("Number of devices found: %i" % (len(self.deviceList)))
		for (k, v) in self.deviceList.iteritems():
			indigo.server.log("\t%s (id: %s)" % (v.label, k))

	def showAvailableDevices(self):
		indigo.server.log("Number of devices found: %i" % (len(self.deviceList)))
		for (id, details) in self.deviceList.iteritems():
			indigo.server.log("\t%s (id: %s)" % (details.label, id))

	def sensorList(self, filter, valuesDict, typeId, targetId):
		#self.debugLog("sensorList called")
		deviceArray = []
		deviceListCopy = deepcopy(self.deviceList)
		for existingDevice in indigo.devices.iter("self"):
			for id in self.deviceList:
				self.debugLog("States: %s" % existingDevice.address)
				
				#self.debugLog("\tcomparing %s against sensorList item %s" % (existingDevice.address,id))
				if str(existingDevice.address) == str(id):
					self.debugLog("\tremoving item %s" % (id))
					del deviceListCopy[id]
					break

		if len(deviceListCopy) > 0:
			for (id,value) in deviceListCopy.iteritems():
				deviceArray.append((id,value.label))
		else:
			if len(self.deviceList):
				indigo.server.log("All devices found are already defined")
			else:
				indigo.server.log("No devices were discovered within Range - select \"Rescan for Sensors\" from the plugin's menu to rescan")

		#self.debugLog("\t DeviceList deviceArray:\n%s" % (str(deviceArray)))
		return deviceArray

	def selectionChanged(self, valuesDict, typeId, devId):
		self.debugLog("SelectionChanged")
		if int(valuesDict["sensor"]) in self.deviceList:
			#self.debugLog("Looking up deviceID %s in DeviceList Table" % valuesDict["sensor"])
			selectedData = self.deviceList[int(valuesDict["sensor"])]
			valuesDict["address"] = valuesDict["sensor"]
			valuesDict["id"] = valuesDict["sensor"]
			valuesDict["sensor"] = valuesDict["sensor"]
			valuesDict["name"] = selectedData.label
			valuesDict["model"] = selectedData.model
			valuesDict["lat"] = selectedData.lat
			valuesDict["lon"] = selectedData.lon
		
		#self.debugLog(u"\tSelectionChanged valuesDict to be returned:\n%s" % (str(valuesDict)))
		return valuesDict

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