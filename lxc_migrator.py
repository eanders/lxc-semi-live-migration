#!/usr/bin/python
from __future__ import with_statement
import argparse
import inspect, os, shutil
import subprocess
import datetime
import socket
import smtplib
import string

__author__ = 'elliot@marlboro.edu (Elliot Anders)'

def main():
	""" Move an LXC container from one host to another with minimal downtime
	:param remote-password: passw0rd [optionally supplied once on the command line/hidden and saved for the duration]
	:param newname: local-container-name [optional] (a new name for the container on the new host)
	:arg remote-host: old-host.domain.tld
	:arg name: container_name (Name of the container you are moving)
	:arg vgname: local volume group that will hold the container 
	
	:todo: eventually [live/freeze/thaw instead of stop/start]
	"""
	
	# Parse arguments
	usage = "usage: %prog [options] remote-host container-name lvm"
	parser = argparse.ArgumentParser(description='Migrate an LXC container to a new host')
	parser.add_argument('remotehost', help="Source host")
	parser.add_argument('containername', help="Source container name (also default destination name)")
	parser.add_argument('vgname', help="Destination Volume Group")
	parser.add_argument("-p", "--password", nargs='?', help="Password for remote-host")
	parser.add_argument("-n", "--new-name", nargs='?', help="Specify a new name for the container after migration")
	args = parser.parse_args()
	
	print args
	
	# todo:
	# [on remote host] fetch size of lvm and vgname from remote host
	# set newcontainer name = old container name if empty
	# lxc-create -n newcontainer -B lvm --vgname vgname --fssize (size from above)
	# mkdir /var/lib/lxc/newcontainer/rootfs/proc
	# mkdir /var/lib/lxc/newcontainer/rootfs/sys
	# mount /dev/vgname/newcontainer /var/lib/lxc/newcontainer/rootfs
	# [on remote host] mount /dev/remotevgname/containername /var/lib/lxc/containername/rootfs
	# rsync -ravH --numeric-ids --delete-delay --delete-excluded --exclude=containername/rootfs/proc --exclude=containername/rootfs/sys -e ssh remote-host:/var/lib/lxc/containername/ /var/lib/lxc/newcontainer
	# [on remote host] unmount /var/lib/lxc/containername/rootfs
	# [on remote host] lxc-shutdown -n containername
	# [on remote host] mount /dev/remotevgname/containername /var/lib/lxc/containername/rootfs
	# rsync -ravH --numeric-ids --delete-delay --delete-excluded --exclude=containername/rootfs/proc --exclude=containername/rootfs/sys -e ssh remote-host:/var/lib/lxc/containername/ /var/lib/lxc/newcontainer
	# umount /var/lib/lxc/newcontainer/rootfs
	# fix /var/lib/lxc/newcontainer/config to reflect new volume group (maybe fstab as well)
	# [on remote host] unmount /var/lib/lxc/containername/rootfs
	# [on remote host] determine if there's an auto start file (and make note of that)
	# [on remote host] rm /etc/lxc/auto/containername.conf
	# lxc-start -d -n newcontainer
	# if it was previously set to auto start, set auto start
	# lxc-list
	
	
if __name__ == "__main__":
	main()