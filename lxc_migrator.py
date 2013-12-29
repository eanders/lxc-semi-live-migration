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

# A convenience method that takes a string or array in the formate expected by subprocess.popen
# and returns the stdout, displaying any stderr if one occurs 
def shell_exec(command):
	#if(isinstance(command, str)):
		#print "executing: " + command
	
	proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	output, errors = proc.communicate()
	if errors:
		raise Exception("ERROR: " + errors)
	return output

class LxcMigrator:
	def __init__(self):
		self._debug = True
		self.user = 'root'
		self.privateKeyFile = '/root/.ssh/id_rsa'
		self.lxcLocation = '/var/lib/lxc'
		self.remoteServer = None
		self.remotePort = 22
		self.remotePassword = None
		self.localContainerName = None
		self.remoteContainerName = None
		self.localVGName = None
		self.remoteLVName = None
		self.lvSize = None
		self.ssh = ssh = paramiko.SSHClient()
		
		""" Move an LXC container from one host to another with minimal downtime
		:param remote-password: passw0rd [optionally supplied once on the command line/hidden and saved for the duration]
		:param newname: local-container-name [optional] (a new name for the container on the new host)
		:arg remote-host: old-host.domain.tld
		:arg name: container_name (Name of the container you are moving)
		:arg vgname: local volume group that will hold the container 
	
		:assumptions: 
			two LXC hosts running ssh with rsync installed either with ssh keys installed for root ssh'ing
			we assume LV sizes are specified in Gigabytes, you may need to adjust
			
		:todo: eventually [live/freeze/thaw instead of stop/start]
		"""
		
		
	def migrate(self):
		self.collectDetails()
		self.checkLocalUser()
		self.getRemoteConfig()
		self.createLocalContainer()
		self.mountLocalContainerFS()
		# todo:
		# [on remote host] fetch size of lvm and vgname from remote host
		# set newcontainer name = old container name if empty
		# lxc-create -n newcontainer -B lvm --vgname vgname --fssize (size from above)
		# mount /dev/vgname/newcontainer /var/lib/lxc/newcontainer/rootfs
		# mkdir /var/lib/lxc/newcontainer/rootfs/proc
		# mkdir /var/lib/lxc/newcontainer/rootfs/sys
		# [on remote host] mount /dev/remoteLVName/containername /var/lib/lxc/containername/rootfs
		# rsync -ravH --numeric-ids --delete-delay --delete-excluded --exclude=containername/rootfs/proc --exclude=containername/rootfs/sys -e ssh remote-host:/var/lib/lxc/containername/ /var/lib/lxc/newcontainer
		# [on remote host] unmount /var/lib/lxc/containername/rootfs
		# [on remote host] lxc-shutdown -n containername
		# [on remote host] mount /dev/remoteLVName/containername /var/lib/lxc/containername/rootfs
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
		parser.add_argument('containername', help='Source container name (also default destination name)')
		parser.add_argument('vgname', help="Destination Volume Group")
		parser.add_argument("-p", "--password", nargs='?', help='Password for remote-host if keys are not available')
		parser.add_argument("-n", "--new-name", nargs='?', help='Specify a new name for the container after migration')
		parser.add_argument("-k", "--private-key-file", nargs='?', help='If your private key file differs from ' + self.privateKeyFile)
		args = parser.parse_args()
	
		self.remoteServer = args.remotehost
		self.remoteContainerName = args.containername
		self.localVGName = args.vgname
		
		if args.password is not None:
			self.remotePassword = args.password
		
		if args.private_key_file is not None:
			self.privateKeyFile = args.private_key_file
			
		self.localContainerName = self.remoteContainerName
		if args.new_name is not None:
			self.localContainerName = args.new_name
		
	def checkLocalUser(self):
		self.user = getpass.getuser()
		if self.user != 'root':
			print "You must run the LXC Migrator as root"
			exit()
	
	def remoteConnect(self):
		self.ssh.load_system_host_keys()
		self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		if self.remotePassword is not None:
			if self._debug:
				print 'Connecting via SSH with password'
			self.ssh.connect(hostname=self.remoteServer, port=self.remotePort, username=self.user, password=self.remotePassword)
		else:	
			if self._debug:
				print 'Connecting via SSH with key file'
			self.ssh.connect(hostname=self.remoteServer, port=self.remotePort, username=self.user, key_filename=self.privateKeyFile)
	
	def remoteDisconnect(self):
		if self._debug:
			print 'Closing SSH connection'
		self.ssh.close()
	
	def getRemoteConfig(self):
		self.remoteConnect()
		cmd = 'cat ' + self.lxcLocation + '/' + self.remoteContainerName + '/config' 
		if self._debug:
			print 'executing: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			if "lxc.rootfs" in line:
				self.remoteLVName = line.split("=")[-1].strip()
		#print self.remoteLVName
		cmd = '/sbin/lvs -o lv_size --noheadings ' + self.remoteLVName
		if self._debug:
			print 'Gathering LVM size: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			self.lvSize = line.strip().rstrip('gGtT')
		self.remoteDisconnect()
	
	def createLocalContainer(self):
		cmd = 'lxc-create -n ' + self.localContainerName + ' -B lvm --vgname ' + self.localVGName + ' --fssize ' + self.lvSize + 'G'
		if self._debug:
			print 'Creating local container: ' + cmd
		shell_exec(cmd)
	
	def mountLocalContainerFS(self):
		cmd = 'mount /dev/' + self.localVGName + '/' + self.localContainerName + ' ' + self.lxcLocation + '/' + self.localContainerName + '/rootfs'
		if self._debug:
			print 'Mounting local lvm: ' + cmd
		shell_exec(cmd)

# run the migration		
migrator = LxcMigrator()
migrator.migrate()
	
	
