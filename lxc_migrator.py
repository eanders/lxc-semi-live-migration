#!/usr/bin/python
from __future__ import with_statement
import argparse
import inspect, os, shutil
import subprocess
import datetime
import socket
import smtplib
import string
import paramiko, base64
import getpass

__author__ = 'elliot@marlboro.edu (Elliot Anders)'

class LxcMigrator:
	def __init__(self):
		self.user = 'root'
		self.privateKeyFile = '/root/.ssh/id_rsa'
		self.remoteServer = None
		self.remotePort = 22
		self.remotePassword = None
		self.localContainerName = None
		self.remoteContainerName = None
		self.localVGName = None
		self.remoteVGName = None
		self.ssh = ssh = paramiko.SSHClient()
		
		""" Move an LXC container from one host to another with minimal downtime
		:param remote-password: passw0rd [optionally supplied once on the command line/hidden and saved for the duration]
		:param newname: local-container-name [optional] (a new name for the container on the new host)
		:arg remote-host: old-host.domain.tld
		:arg name: container_name (Name of the container you are moving)
		:arg vgname: local volume group that will hold the container 
	
		:assumptions: two LXC hosts running ssh with rsync installed either with ssh keys installed for root ssh'ing
	
		:todo: eventually [live/freeze/thaw instead of stop/start]
		"""
		
		
	def migrate(self):
		self.collectDetails()
		self.checkLocalUser()
		self.getRemoteConfig()
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
	
		
	def collectDetails(self):
		# Parse arguments
		usage = "usage: %prog [options] remote-host container-name lvm"
		parser = argparse.ArgumentParser(description='Migrate an LXC container to a new host')
		parser.add_argument('remotehost', help="Source host")
		parser.add_argument('containername', help="Source container name (also default destination name)")
		parser.add_argument('vgname', help="Destination Volume Group")
		parser.add_argument("-p", "--password", nargs='?', help="Password for remote-host if keys are not available")
		parser.add_argument("-n", "--new-name", nargs='?', help="Specify a new name for the container after migration")
		args = parser.parse_args()
	
		self.remoteServer = args.remotehost
		if args.password is not None:
			self.remotePassword = args.password
		if args.new_name is not None:
			self.localContainerName = args.new_name
		self.remoteContainerName = args.containername
		self.localVGName = args.vgname
		
	def checkLocalUser(self):
		self.user = getpass.getuser()
		if self.user != 'root':
			print "You must run the LXC Migrator as root"
			exit()
	
	def remoteConnect(self):
		self.ssh.load_system_host_keys()
		self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		if self.remotePassword is not None:
			self.ssh.connect(hostname=self.remoteServer, port=self.remotePort, username=self.user, password=self.remotePassword)
		else:
			self.ssh.connect(hostname=self.remoteServer, port=self.remotePort, username=self.user, key_filename=self.privateKeyFile)
	
	def remoteDisconnect(self):
		self.ssh.close()
	
	def getRemoteConfig(self):
		self.remoteConnect()
		stdin, stdout, stderr = self.ssh.exec_command('ls /usr/local/sbin')
		for line in stdout:
			print '... ' + line.strip('\n')
		self.remoteDisconnect()
	
	
migrator = LxcMigrator()
migrator.migrate()
	