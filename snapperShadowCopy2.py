#! /usr/bin/env python3
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
#     - get the folder where symlinks are to be created from "shadow:snapdir" option smb.conf
#       Needs some testing with samba 3.6.6 an according shadwCopy2 module as initial testing was done on samba4
#
#    - commenting the functions
#    - add a loging facility / done, but can always be improved
#    - daemonize the script
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

import logging

LOG_FILENAME = os.path.dirname(os.path.realpath(__file__)) + '/snapperShadowCopy2.log'
LOG_LEVEL = logging.DEBUG # Maybe: logging.DEBUG / logging.INFO / logging.ERROR / logging.WARNING
logging.basicConfig(filename=LOG_FILENAME, format='%(asctime)s-%(levelname)s-%(funcName)s: %(message)s', level=LOG_LEVEL)

snapperConfig = collections.namedtuple('snapperConfig', 'Name Path AttrNumber')
# namedtuple to hold single 'snapperd' config object """
snapperSnapshot = collections.namedtuple('snapperSnapshot', 'snapId snapType snapPreviousId snapCreationTime snapCreatorUid snapDescription, snapCleanup snapDict')
# namedtuple to hold single 'snapperd' snapshot object """

#Initialization of needed components
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
    
snapperIface = dbus.Interface(bus.get_object('org.opensuse.Snapper', '/org/opensuse/Snapper'), dbus_interface='org.opensuse.Snapper')
# init the snapper dbus Interface for communication with 'snapperd' daemon """


def main():
    global vfsEnabledSmbShares
    
    bus.add_signal_receiver(onSnapCreated, dbus_interface="org.opensuse.Snapper", signal_name="SnapshotCreated")
    logging.debug('Added signal receiver for snapper ''SnapshotCreated'' dBus-Signal')
    bus.add_signal_receiver(onSnapsDeleted, dbus_interface="org.opensuse.Snapper", signal_name="SnapshotsDeleted")
    logging.debug('Added signal receiver for snapper ''SnapshotsDeleted'' dBus-Signal')
    bus.add_signal_receiver(onSmbConfChanged, dbus_interface="com.example.Sample", signal_name="smbConfChanged")
    logging.debug('Added signal receiver for selfCreated smConfWatcher ''smbConfChanged'' dBus-Signal')

    vfsEnabledSmbShares = getSmbShadowCopyEnabledPathes()
    logging.info('using share pathes for comparision: ' + str(vfsEnabledSmbShares))
    
    onStartCleanupSymlinks()
    
    mainloop = glib.MainLoop()

    try:
        mainloop.run()
    except KeyboardInterrupt:
           
        mainloop.quit()


        
def onStartCleanupSymlinks():
    
    logging.info("Startup Cleaning of symlinks that are no longer existant")
    configs = getSnapperConfigs()
    logging.info(str(configs))
    for cfg in configs:
        config = snapperConfig._make(cfg)
        logging.info("Cleaning symlinks for " + config.Path)
        deleteSymlinks(config.Path+'/.vfs')
        
        logging.info("retrieving snapshot list for snapper config  " + config.Name)
        snapshots = getSnapshotsList(config.Name)
        for snap in snapshots:
            if not snap[0] == 0: #snapId 0 refers to the 'current' so we don't need a symlink here
                logging.debug("retrieving snapshot with id: " + str(snap[0]))
                snapshot = getSnapperSnapshot(config.Name, snap[0])
                createSymlink(snapshot, config.Path, config.Name)       

def onSnapCreated(configName, snapshotId):
    """ Handler function for the 'snapperd' dbus signal 'SnapshotCreated'
        creating symlink to the newly created 'snapper snapshot' in
        '%PathToShare%/%snapDir%/@GMT-"%Y.%m.%d-%H.%M.%S' so that the
        snapshot is recognized by the samba vfs module shadowCopy2.
        Symlinks are only created for shares that are configured with
        with the 'vfs objects = shadowCopy2' option in 'smb.conf'"""
    
    logging.debug('received dBus signal ''SnapshotCreated'' with values: ' + str(configName) + ' / ' + str(snapshotId))
    config = getSnapperConfig(configName)
    logging.info(str(config))
    logging.info("comparing snapper Snapshot path with pathes read from smbconf")
    logging.info("snapper Snapshot base subvolume path: " + config.Path)
    logging.info("smbConf share pathes: ")
    for path in vfsEnabledSmbShares:
        logging.info(path)

    if config.Path in vfsEnabledSmbShares:
        # Needs improvement so that the path configured by "shadow:snapdir" in smb.conf gets created if does not exist
        snapshot = getSnapperSnapshot(configName, snapshotId)
        logging.debug("snapshot information returned from from snapper dBus" + str(snapshot))
        createSymlink(snapshot, config.Path, config.Name)
    else:
        logging.info("No 'shadowCopy2' enabled smb share found with path '"+config.Path+"' !")
        logging.info("Nothing to do...")


def createSymlink(snapshot, basePath, configName):
    ts = datetime.datetime.fromtimestamp(snapshot.snapCreationTime)
    linkTarget = str(basePath) +"/.snapshots/"+str(snapshot.snapId)+"/snapshot"
    linkPath = str(basePath) +"/.vfs/@GMT-"+ts.strftime("%Y.%m.%d-%H.%M.%S")
    # needs improvement so this path gets read from smb.conf
   
    if not os.path.lexists(linkPath):
        logging.info("creating symlink: " +  linkPath + " --> " + linkTarget)
        logging.info("from following information:")
        logging.info("config.Name: " + configName)
        logging.info("snapshot.snapId: " + str(snapshot.snapId))
        
        os.symlink(linkTarget, linkPath)
        logging.info("Symlink has been created!")
    else:
        logging.info("There was no symlink to be created")

def deleteSymlinks(basePath):
    if os.path.isdir(basePath):
        links = os.listdir(basePath)
        #Should return only symlinks as this folder should be used for nothing else...

        for link in links:
            fullpath = basePath+"/"+link
            targetPath = os.readlink(fullpath)
            if not os.path.exists(fullpath):
                os.unlink(fullpath)
                logging.info("symlink " +link+ " for deleted snapshot: " + targetPath + " was removed")
    else:
        logging.info("'" + basePath + "' does not exist, no action to do")
        logging.info("Nothing to do...")
        
def onSnapsDeleted(configName, message):
    """ Handler function for the 'snapperd' dbus signal 'SnapshotDeleted'
        Cleaning up unused symlinks that are broken after the snapshot deletion
        by 'snapperd'"""
 
    logging.debug('received dBus signal ''SnapshotDeleted'' with values: ' + str(configName) + ' / ' + str(message))
    config = getSnapperConfig(configName)
    logging.info(config.Name + " /" + str(message))
    path = config.Path+"/.vfs/"
    #needs improvement to get path from smbConf
    deleteSymlinks(path, message[0])
    

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

def onSmbConfChanged(message):
    logging.debug('received dBus signal ''smbconfChanged'' :OK lets do something on smbConfChanged event')
    logging.info('re-reading smbConf to read configured shares')
    vfsEnabledSmbShares = getSmbShadowCopyEnabledPathes()
    logging.info("using share pathes from smb.conf for comparision: " + str(vfsEnabledSmbShares))

def getSmbShadowCopyEnabledPathes():
    # List gets filled with share pathes that have the searched option set with the searched value / array is used as return value
    sharePathes = []
    configFile = "/etc/samba/smb.conf"
    vfsOption = "vfs objects"
    vfsSearchValue = "shadow_copy2"

    Config = ConfigParser.ConfigParser()
    Config.read(configFile)
    sections = Config.sections()
    logging.info("reading smb.conf")
    for section in sections:
        if section != "global":
            logging.info('searching in section: ' + section)
            options = Config.options(section)
            for option in options:
                logging.debug(section + "  :  " + option + "=" +Config.get(section, option))
                if option == vfsOption:
                    try:
                        optionValue = Config.get(section, option)
                        #print optionValue
                        if optionValue in vfsSearchValue:
                            logging.info('found option #' + option + '# with value: ' + optionValue)
                            sharePathes.append(Config.get(section, "path"))

                    except:
                        logging.debug("exception on %s!" % option)
    logging.debug('smb.conf reading complete')
    return sharePathes


    
if __name__ == '__main__':
    main()
    

    
