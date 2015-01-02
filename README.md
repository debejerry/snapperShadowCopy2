snapperShadowCopy2
==================
-->>   Caution  <<--

This script is in ALPHA Status !
Use it at your own Risk!!!
Only Use it if you understand what it is doing!!


How to install snapperShadowCopy2?

so far an install script is going to be developed but it is not ready atm.
You have to to do some things manually to get it working (see dependencies).

Does this script have dependencies?

Yes, it does. It has some python depencies as well as dependencies on other packages:
  Python dependencies:
    - python3-gi (see -> https://packages.debian.org/de/wheezy/python/python3-gi )
    - python-dbus (see -> https://packages.debian.org/de/wheezy/python/python-dbus )
    
  Other Packages (without them this script might get useless...):
    - "btrfs-tools" (until now only tested with latest btrfs-tools package (btrfs-tools (3.14.1-1~bpo70+1)
      from debian wheezy backports -> https://packages.debian.org/wheezy-backports/btrfs-tools )
    - "snapper" (see -> http://snapper.io/ and 
      "http://software.opensuse.org/download/package?project=filesystems:snapper&package=snapper"
      for instructions on how to install the "snapper" package on debian wheezy
    - "samba" >= 3.6.6 includng vfs module shadowCopy2
      the shadowCopy2 module needs to be enabled on a per share basis see ->       
      "https://www.samba.org/samba/docs/man/manpages/vfs_shadow_copy2.8.html"
      for usage options.
      
How to use this script?
If all dependencies are installed, things should be easy:
  - mount your btrfs volume i.e. to "/btrfs/volume1"
  - create a snapper config "snapper -c myConfigName create-config /btrfs/volume1"
    creating a default config enables timeline snapshots, i.e. 10 hourlies, 10 dailies and s.o.
  - set up the smb share for "/btrfs/volume1" 
    - make sure the 'path' option for your share is the same as the path your snapper config refers to:
    smb.conf:
      [global]
      unix_etensions = no
      [myShare]
      path = /btrfs/volume1 #needs to be the sam as in the "snapper -c myConfigName create-config /btrfs/volume1" cmd
      vfs objects = shadowCopy2
      shadow:snapdir = .vfs # is an example path that would refer to "/btrfs/volume1/.vfs"
      shadow:basedir = /btrfs/volume1
      # for samba 3.6.6 do not use the option "shadow:localtime = yes/no" 
      # no idea why but breaks snapshot visibilty in Windows Explorer
  
  - restart samba
  - run snapperShadowCopy2.py: 
      #:> python3 /%scriptPath%/snapperShadowCopy2.py
  - on a 2nd (if not sent to background) create a new snapshot: 
      #:> snapper -c myConfigName create
    the btrfs snapshot will be created and available through: "/btrfs/volume1/.snapshots/#snapID#/snapshot"
  - snapperShadowCopy2 will detect the snapshot creation by snapper and adds a symlink to your /btrfs/volume1/.vfs" 
    folder that will look like: '@GMT-"%Y.%m.%d-%H.%M.%S' for resulting symlink:
    "/btrfs/volume1/.vfs/@GMT-2014.12.28-14.33.45"
  - browse your share through Windows Explorer and check the "previous versions" tab it should show you the snapshot      you just created
  - 

