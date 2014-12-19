#! /usr/bin/python
# -*- coding: utf-8 -*-
#Copyright (C) 2014 OpenMediaVault Plugin Developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# -------- To Do List -------
# 	- get the folder where symlinks are to be created from "shadow:snapdir" option smb.conf
#	   Needs some testing with samba 3.6.6 an according shadwCopy2 module as initial testing was done on samba4
#
#	- commenting the functions
#	- add a loging facility 
#	- daemonize the script
#	
#
#

import os
import collections
import time
import datetime
import ConfigParser

import dbus
import glib
from dbus.mainloop.glib import DBusGMainLoop


#Initialization of needed components
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
snapperIface = dbus.Interface(bus.get_object('org.opensuse.Snapper', '/org/opensuse/Snapper'), dbus_interface='org.opensuse.Snapper')
# init the snapper dbus Interface for communication with 'snapperd' daemon """


snapperConfig = collections.namedtuple('snapperConfig', 'Name Path AttrNumber')
# namedtuple to hold single 'snapperd' config object """
snapperSnapshot = collections.namedtuple('snapperSnapshot', 'snapId snapType snapPreviousId snapCreationTime snapCreatorUid snapDescription, snapCleanup snapDict')
# namedtuple to hold single 'snapperd' snapshot object """




def onSnapCreated(configName, snapshotId):
	""" Handler function for the 'snapperd' dbus signal 'SnapshotCreated'
		creating symlink to the newly created 'snapper snapshot' in
		'%PathToShare%/%snapDir%/@GMT-"%Y.%m.%d-%H.%M.%S' so that the
		snapshot is recognized by the samba vfs module shadowCopy2.
		Symlinks are only created for shares that are configured with
		with the 'vfs objects = shadowCopy2' option in 'smb.conf'"""
	print str(configName) + " / " + str(snapshotId)
	
	config = getSnapperConfig(configName)
	print "Is " + config.Path"
	print "contained in:"
	for path in vfsEnabledSmbShares
		print path
		
	if config.Path in vfsEnabledSmbShares:
# Needs improvement so that the path configured by "shadow:snapdir" in smb.conf gets created if does not exist 
		snapshot = getSnapperSnapshot(configName, snapshotId)
		print str(snapshot)
		ts = datetime.datetime.fromtimestamp(snapshot.snapCreationTime)
		linkTarget = str(config.Path) +"/.snapshots/"+str(snapshotId)+"/snapshot"
		linkPath = str(config.Path) +"/.vfs/@GMT-"+ts.strftime("%Y.%m.%d-%H.%M.%S")
		print "creating symlink:"
		print linkPath + " --> " + linkTarget
		print "from:"
		print "config.Name: " + config.Name
		print "snapshot.snapId: " + str(snapshot.snapId)
		if not os.path.lexists(linkPath):
			os.symlink(linkTarget, linkPath)
			print "Symlink has been created!"
	else:
		print "No 'shadowCopy2' enabled smb share found with path '"+config.Path+"' !"
		print "Nothing to do..."
			

def onSnapsDeleted(configName, message):
	""" Handler function for the 'snapperd' dbus signal 'SnapshotDeleted'
		Cleaning up unused symlinks that are broken after the snapshot deletion
		by 'snapperd'"""
	config = getSnapperConfig(configName)
	print config.Name + " /" + str(message)
	path = config.Path+"/.vfs/"
	if os.path.isdir(path):
		links = os.listdir(path)
		#Should return only symlinks as this folder should be used for nothing else...

		for link in links:
			fullpath = path+"/"+link
			if not os.path.exists(fullpath):
				os.unlink(fullpath)
				print "symlink " +link+ " for deleted snapshotId: " + str(message[0]) + " was removed"
	else:
		print "'" + path + "' does not exist, no action to do"
		print "Nothing to do..."

def getSnapperConfigs():	
	configs = snapperIface.ListConfigs()
	return configs
	
def getSnapperConfig(configName):
	config = snapperConfig._make(snapperIface.GetConfig(configName))
	return config
		
def getSnapshotsList(configName):
	snapshots = snapperIface.ListSnapshots(configName)
	return snapshots

def getSnapperSnapshot(configName, snapId):
	snapshot = snapperSnapshot._make(snapperIface.GetSnapshot(configName, snapId))
	return snapshot
	


def getSmbShadowCopyEnabledPathes():
    # List gets filled with share pathes that have the searched option set with the searched value / array is used as return value
	sharePathes = [] 
	configFile = "/etc/samba/smb.conf"
	vfsOption = "vfs objects"
	vfsSearchValue = "shadow_copy2"
	
	Config = ConfigParser.ConfigParser()
	Config.read(configFile)
	sections = Config.sections()

	for section in sections:
		if section != "global":
			options = Config.options(section)
			for option in options:
				if option == vfsOption:
					try:
						optionValue = Config.get(section, option)
						if optionValue in vfsSearchValue:
							sharePathes.append(Config.get(section, "path"))
							
					except:
						print("exception on %s!" % option)
	
	return sharePathes
	
vfsEnabledSmbShares = getSmbShadowCopyEnabledPathes()
# List used for storing pathes to smb shares that have 'shadowCopy2' enabled in smb.conf """
# Thought: Maybe this should get it's own module....


bus.add_signal_receiver(onSnapCreated, dbus_interface="org.opensuse.Snapper", signal_name="SnapshotCreated")
bus.add_signal_receiver(onSnapsDeleted, dbus_interface="org.opensuse.Snapper", signal_name="SnapshotsDeleted")


mainloop = glib.MainLoop()
mainloop.run()
