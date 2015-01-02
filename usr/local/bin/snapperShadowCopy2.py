#! /usr/bin/python3

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
#    - commenting the functions
#    - daemonize the script
#
#
#

import os
import signal
import collections
import time
import datetime
import configparser
import sys

import dbus
from gi.repository import GObject
from gi.repository import GLib
from gi.repository import Gio
from dbus.mainloop.glib import DBusGMainLoop

import logging

#import smbConfNotify2

LOG_FILENAME = os.path.dirname(os.path.realpath(__file__)) + '/snapperShadowCopy2.log'
LOG_LEVEL = logging.INFO # Maybe: logging.DEBUG / logging.INFO / logging.ERROR / logging.WARNING
LOG_FORMAT = '%(asctime)s-%(levelname)-5s-%(funcName)-15s: %(message)s'
#old LOG_FORMAT #'%(asctime)s-%(levelname)s-%(funcName)s: %(message)s'
logging.basicConfig(filename=LOG_FILENAME, format=LOG_FORMAT, level=LOG_LEVEL)

snapperConfig = collections.namedtuple('snapperConfig', 'Name Path AttrNumber')
# namedtuple to hold single 'snapperd' config object """
snapperSnapshot = collections.namedtuple('snapperSnapshot', 'snapId snapType snapPreviousId snapCreationTime snapCreatorUid snapDescription, snapCleanup snapDict')
# namedtuple to hold single 'snapperd' snapshot object """
smbConfOptions = collections.namedtuple('smbConfOptions', 'Path snapDir')

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
    logging.info('using share pathes for comparision: ' + str(list(vfsEnabledSmbShares.keys())))    

    smbConfPath = '/etc/samba/smb.conf'
    # Enable File Monitoring on sm.conf
    gio_file = Gio.File.new_for_path(smbConfPath)
    monitor = gio_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
    monitor.connect("changed", onSmbConfChanged)
       
    onStartCleanupSymlinks()
       
    global loop
    loop = GObject.MainLoop()
   # for signal handling: refer to : http://stackoverflow.com/questions/26388088/python-gtk-signal-handler-not-working
    GObject.threads_init()
    InitSignal(loop) # connect to System signals as definied through InitSignal() and sub functions
    loop.run()
    
        
def onStartCleanupSymlinks():
    global vfsEnabledSmbShares
    logging.debug("Startup Cleaning of symlinks that are no longer existant")
    configs = getSnapperConfigs()
    logging.debug(str(configs))
    for cfg in configs:
        config = snapperConfig._make(cfg)
        logging.info("Cleaning symlinks for " + config.Path)
        shareOptions = smbConfOptions._make(vfsEnabledSmbShares[str(config.Path)])
        deleteSymlinks(config.Path+'/'+shareOptions.snapDir)
        
        logging.info("retrieving snapshot list for snapper config  " + config.Name)
        logging.info("creating missing symlinks on ''%s''" % config.Path)
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
    global vfsEnabledSmbShares
    logging.debug('received dBus signal ''SnapshotCreated'' with values: ' + str(configName) + ' / ' + str(snapshotId))
    config = getSnapperConfig(configName)
    logging.info(str(config))
    logging.info("comparing snapper Snapshot path with pathes read from smbconf")
    logging.info("snapper Snapshot base subvolume path: " + config.Path)
    logging.info("smbConf share pathes: ")
    for path in list(vfsEnabledSmbShares.keys()):
        logging.info(path)

    if config.Path in list(vfsEnabledSmbShares.keys()):
        # Needs improvement so that the path configured by "shadow:snapdir" in smb.conf gets created if does not exist
        snapshot = getSnapperSnapshot(configName, snapshotId)
        logging.debug("snapshot information returned from from snapper dBus" + str(snapshot))
        createSymlink(snapshot, config.Path, config.Name)
    else:
        logging.info("No 'shadowCopy2' enabled smb share found with path '"+config.Path+"' !")
        logging.info("Nothing to do...")

def createSymlink(snapshot, basePath, configName):
    global vfsEnabledSmbShares
    ts = datetime.datetime.fromtimestamp(snapshot.snapCreationTime)
    linkTarget = str(basePath) +"/.snapshots/"+str(snapshot.snapId)+"/snapshot"
    shareOptions = smbConfOptions._make(vfsEnabledSmbShares[basePath])
    # Expand Share Options to retrieve the snapdir value
    linkPath = str(basePath) +'/'+ shareOptions.snapDir +'/@GMT-'+ts.strftime("%Y.%m.%d-%H.%M.%S")
    if not os.path.lexists(linkPath):
        logging.info("creating symlink: " +  linkPath + " --> " + linkTarget)
        logging.debug("from following information:")
        logging.debug("config.Name: " + configName)
        logging.debug("snapshot.snapId: " + str(snapshot.snapId))
        
        os.symlink(linkTarget, linkPath)
        logging.debug("Symlink has been created!")
    else:
        logging.debug("There was no symlink to be created for SnapID" + str(snapshot.snapId))

def deleteSymlinks(basePath):
    if os.path.isdir(basePath):
        links = os.listdir(basePath)
        #Should return only symlinks as this folder should be used for nothing else...
        logging.info("deleting leftover symlinks on ''%s''" % basePath)
      
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
    global vfsEnabledSmbShares
    logging.debug('received dBus signal ''SnapshotDeleted'' with values: ' + str(configName) + ' / ' + str(message))
    config = getSnapperConfig(configName)
    logging.info(config.Name + " /" + str(message))
    shareOptions = smbConfOptions._make(vfsEnabledSmbShares[config.Path])
    path = config.Path + '/' + shareOptions.snapDir
    #needs improvement to get path from smbConf
    deleteSymlinks(path)
    

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

def onSmbConfChanged(m, f, o, event):
    global vfsEnabledSmbShares
    if event == Gio.FileMonitorEvent.CHANGED:
        logging.info('smb.conf has changed')
        logging.info('re-reading smbConf to read configured shares')
       
        vfsEnabledSmbShares = getSmbShadowCopyEnabledPathes()
        logging.info("using share pathes from smb.conf for comparision: " + str(vfsEnabledSmbShares))
    else:
        logging.debug(m)
        logging.debug(f)
        logging.debug(o)
        logging.debug(event)

def getSmbShadowCopyEnabledPathes():
    # List gets filled with share pathes that have the searched option set with the searched value / array is used as return value
    sharePathes = dict()
    configFile = "/etc/samba/smb.conf"
    vfsOption = "vfs objects"
    vfsSearchValue = "shadow_copy2"

    Config = configparser.ConfigParser(interpolation=None, strict=False, delimiters=('='))
    Config.read(configFile)
    sections = Config.sections()
    logging.info("reading smb.conf")
    for section in sections:
        if section != "global":
            logging.info('searching in section: ' + section)
            options = Config.options(section)
            for option in options:
                logging.debug(section + "  :  " + option + "=" +Config.get(section, option))
                optionValue = Config.get(section, option)
                #print(option + '&' + optionValue) 
                if option == vfsOption:
                    try:
                        
                        
                        if optionValue in vfsSearchValue:
                            logging.info('found option #' + option + '# with value: ' + optionValue)
                            tmpSmbPath = Config.get(section, "path").rstrip('/')
                            #Get this share options into dictionary / remove trailing slash if it is there 
                            sharePathes[tmpSmbPath] = smbConfOptions._make([tmpSmbPath, Config.get(section, 'shadow:snapdir')])
                            
                    except Exception as e:
                    # If smb.conf option shadow:snapdir is not found it should be set to a default value, 
                    # or at least user should get notified that there is a missing option in the smb.conf section of this share
                        logging.debug("exception on %s!" % option)
                        logging.debug(str(e))
    logging.debug('smb.conf reading complete')
 
    return sharePathes

def InitSignal(loop):
    def signal_action(signal):
        logging.debug('signal_action() called with value:' + signum_toname(signal))
                  
        if signal is 1:
            logging.debug("Caught signal SIGHUP(1)")
        elif signal is 2:
            logging.info("SIGINT(2) recieved")
            #smbConfWatcher.stopLoop()
            #time.sleep(2)
            logging.info('exit snapperShadowCopy2')
            logging.debug('Exiting mainloop')
            loop.quit()
            logging.debug('Doing sys.exit(0)')
            sys.exit(0)
        elif signal is 15:
            logging.info("SIGTERM(15) recieved")
            #smbConfWatcher.stopLoop()
            #time.sleep(2)
            logging.info('exit snapperShadowCopy2')
            logging.debug('Exiting mainloop')
            loop.quit()
            logging.debug('Doing sys.exit(0)')
            sys.exit(0)
        
    def idle_handler(*args):
        logging.debug("Python signal handler activated.")
        logging.debug('idle_handler() got args:')
        for count, thing in enumerate(args):
            logging.debug('{0}. {1}'.format(count, thing))
        GLib.idle_add(signal_action, args[0], priority=GLib.PRIORITY_HIGH)

        
    SIGS = [getattr(signal, s, None) for s in "SIGINT SIGTERM SIGHUP".split()]
    for sig in filter(None, SIGS):
        logging.debug("Register Python signal handler: %r" % sig)
        signal.signal(sig, idle_handler)
        
def signum_toname(num):
    name = []
    for key in signal.__dict__.keys():
        if key.startswith("SIG") and getattr(signal, key) == num:
            name.append (key)
    if len(name) == 1:
        return name[0]
    else:
        return str(num)

if __name__ == '__main__':
    main()
    

    
