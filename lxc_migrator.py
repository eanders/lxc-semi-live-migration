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
		self.lxcAutoStartDirectory = '/etc/lxc/auto'
		self.remoteServer = None
		self.remotePort = 22
		self.remotePassword = None
		self.localContainerName = None
		self.remoteContainerName = None
		self.autoStart = False
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
		self.createProcSysDirectories()

		# first pass
		self.mountRemoteContainerFS()
		self.rsyncFromRemote()
		self.unmountRemoteContainerFS()
		self.stopRemoteContainer()
		# second pass
		self.mountRemoteContainerFS()
		self.rsyncFromRemote()
		self.unmountRemoteContainerFS()
		
		self.unMountLocalContainerFS()
		self.fixLocalConfig()
		self.startLocalContainer()
		self.setAutoStart()
		self.lxcList()
		print 'Migration complete.'
		print 'You will need to manually remove the remote container if the migration was successfull'
		
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
		# fix /var/lib/lxc/newcontainer/config to reflect new volume group
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
		cmd = 'cat {self.lxcLocation}/{self.remoteContainerName}/config'.format(self=self) 
		if self._debug:
			print 'Looking for the remote lv name: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			if "lxc.rootfs" in line:
				self.remoteLVName = line.split("=")[-1].strip()
		#print self.remoteLVName
		cmd = '/sbin/lvs -o lv_size --noheadings {self.remoteLVName}'.format(self=self)
		if self._debug:
			print 'Gathering LVM size: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			self.lvSize = line.strip().rstrip('gGtT')
		# see if we have an auto start file
		cmd = 'ls -1 {self.lxcAutoStartDirectory}'.format(self=self)
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			print line
			if line == '{self.remoteContainerName}.conf'.format(self=self):
				self.autoStart = True
		self.remoteDisconnect()
	
	def createLocalContainer(self):
		cmd = 'lxc-create -n {self.localContainerName} -B lvm --vgname {self.localVGName} --fssize {self.lvSize}G'.format(self=self)
		if self._debug:
			print 'Creating local container: ' + cmd
		try:
			shell_exec(cmd)
		except Exception as e:
			print "lxc-create error (you probably already have a logical volume of this name): {0}".format(e)
			exit()
			
	def mountLocalContainerFS(self):
		cmd = 'mount /dev/{self.localVGName}/{self.localContainerName} {self.lxcLocation}/{self.localContainerName}/rootfs'.format(self=self)
		if self._debug:
			print 'Mounting local lvm: ' + cmd
		shell_exec(cmd)
	
	def unMountLocalContainerFS(self):
		cmd = 'umount {self.lxcLocation}/{self.localContainerName}/rootfs'.format(self=self)
		if self._debug:
			print 'Unmounting local lvm: ' + cmd
		shell_exec(cmd)
	
	def createProcSysDirectories(self):
		cmd =  'mkdir {self.lxcLocation}/{self.localContainerName}/rootfs/proc'.format(self=self)
		if self._debug:
			print 'Creating empty proc directory: ' + cmd
		shell_exec(cmd)
		cmd =  'mkdir {self.lxcLocation}/{self.localContainerName}/rootfs/sys'.format(self=self)
		if self._debug:
			print 'Creating empty sys directory: ' + cmd
		shell_exec(cmd)
		
	def mountRemoteContainerFS(self):
		self.remoteConnect()
		# [on remote host] mount /dev/remoteLVName/containername /var/lib/lxc/containername/rootfs
		cmd = 'mount {self.remoteLVName} {self.lxcLocation}/{self.remoteContainerName}/rootfs'.format(self=self)
		if self._debug:
			print 'Mounting remote container file system: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			print line
		self.remoteDisconnect()

	def rsyncFromRemote(self):
		cmd = 'rsync -raH --numeric-ids --delete-delay --exclude={self.localContainerName}/rootfs/proc --exclude={self.localContainerName}/rootfs/sys -e "ssh -i {self.privateKeyFile}" {self.remoteServer}:{self.lxcLocation}/{self.remoteContainerName}/  {self.lxcLocation}/{self.localContainerName}'.format(self=self)
		if self._debug:
			print 'Rsyncing: ' + cmd
		shell_exec(cmd)
		
	def unmountRemoteContainerFS(self):
		self.remoteConnect()
		# [on remote host] umount /var/lib/lxc/containername/rootfs
		cmd = 'umount {self.lxcLocation}/{self.remoteContainerName}/rootfs'.format(self=self)
		if self._debug:
			print 'Unmounting remote container file system: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			print line
		self.remoteDisconnect()

	def stopRemoteContainer(self):
		self.remoteConnect()
		cmd = 'lxc-shutdown -n {self.remoteContainerName}'.format(self=self)
		if self._debug:
			print 'Shutting down remote container: ' + cmd
		stdin, stdout, stderr = self.ssh.exec_command(cmd)
		for line in stdout:
			print line
		self.remoteDisconnect()
		
	def startLocalContainer(self):
		cmd = 'lxc-start -d -n {self.localContainerName}'.format(self=self)
		if self._debug:
			print 'Starting local container: ' + cmd
		shell_exec(cmd)
		
	def fixLocalConfig(self):
		filename = '{self.lxcLocation}/{self.localContainerName}/config'.format(self=self)
		localLVPath = '/dev/{self.localVGName}/{self.localContainerName}'.format(self=self)
		if self._debug:
			print 'replacing {self.remoteLVName} with {localLVPath} in {filename}'.format(self=self, localLVPath=localLVPath, filename=filename)
		s = open(filename).read()
		s = s.replace(self.remoteLVName, localLVPath)
		f = open(filename, 'w')
		f.write(s)
		f.close()
		
	def setAutoStart(self):
		if self.autoStart:
			cmd = 'ln -s {self.lxcLocation}/{self.localContainerName}/config {self.lxcAutoStartDirectory}/{self.localContainerName}.conf'.format(self=self)
			if self._debug:
				print 'Setting container to auto start: ' + cmd
			shell_exec(cmd)
			self.remoteConnect()
			cmd = 'rm {self.lxcAutoStartDirectory}/{self.remoteContainerName}.conf'.format(self=self)
			if self._debug:
				print 'removing auto start from remote container: ' + cmd
			stdin, stdout, stderr = self.ssh.exec_command(cmd)
			for line in stdout:
				print line
			self.remoteDisconnect()
	
	def lxcList(self):
		cmd = 'lxc-list'
		print shell_exec(cmd)
	
# run the migration		
migrator = LxcMigrator()
migrator.migrate()
	
	
