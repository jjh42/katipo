# ===========================================================================
#
#  COPYRIGHT 2012-2013 Brain Corporation.
#  License under MIT license (see LICENSE file)
# =============================================================================

import os
import git
import logging
import json
import sys
import shutil
import subprocess
import tempfile


class KatipoException(Exception):
	pass


class Assembly(object):
	"""Class for dealing with assembly files.

	Initialize with a JSON (+ # comments)
	description of an assembly file."""
	def __init__(self, content):
		self._parse_assembly_file(content)
		if self.description['version'] != 1:
			# Only recognise one schema at the moment
			raise KatipoException('Unknown katipo version %s' %
								str(self.description['version']))
		self.repos = self.description['repos']

	def _parse_assembly_file(self, content):
		lines = content.split('\n')
		lines = [l for l in lines if len(l) != 0 and l[0] != '#']
		self.description = json.loads('\n'.join(lines) + '\n')


class KatipoRoot(object):
	"""Class for interacting with a Katipo repo. It must either be passed
	a folder from which to search for a ketapo root or a giturl and assembly
	file."""
	def __init__(self, folder=None, giturl=None, assemblyfile=None):
		assert(folder is not None)
		if giturl is None:
			logging.info('Creating katipo from prexisting root')
			assert(assemblyfile is None)
			self._find_katipo_root(folder)
			self._reload_katipo_root()
		else:
			logging.info('Clone new katipo root')
			assert(assemblyfile is not None)
			try:
				self._clone(folder, giturl, assemblyfile)
			except:
				exc_info = sys.exc_info()
				if hasattr(self, '_katipo_root'):
					logging.warning('Removing incomplete katipo root %s' %
								self._katipo_root)
					try:
						shutil.rmtree(self._katipo_root)
					except:
						pass
				raise exc_info[1], None, exc_info[2]

	def _find_katipo_root(self, folder):
		"""Load in a katipo setup."""
		# Start from folder and find the root
		# Ensure we check this folder first
		last_checked = None
		while folder != last_checked:
			if os.path.exists(os.path.join(folder, '.katipo')):
				logging.info('Found katipo root in %s' % folder)
				self._working_copy_root = folder
				self._katipo_root = os.path.join(folder, '.katipo')
				return
			last_checked = folder
			folder = os.path.split(folder)[0]
		raise KatipoException('Unable to find .katipo root')

	def _reload_katipo_root(self):
		"""Reload the assembly file."""
		self._load_assembly()

	def _load_assembly(self):
		self.assembly = Assembly(open(os.path.join(os.path.join(
								self._katipo_root, 'assembly_file'))).read())

	def _clone(self, folder, assembly_giturl, assemblyfile):
		"""Initial a katipo setup in folder from assemblyfile in
		assembly_giturl."""
		logging.info('Cloning into %s from %s:/%s' %
					(folder, assembly_giturl, assemblyfile))
		self._create_katipo_root_folder(folder)
		self._assembly_repo = git.Repo.clone_from(assembly_giturl,
								os.path.join(self._katipo_root, 'assembly'))
		# Create a symlink to the assembly file to use
		os.symlink(os.path.join(self._katipo_root, 'assembly', assemblyfile),
				os.path.join(self._katipo_root, 'assembly_file'))
		self._load_assembly()
		for repo_params in self.assembly.repos:
			# Clone each repo
			repo = git.Repo.clone_from(repo_params['giturl'],
									os.path.join(self._working_copy_root,
									repo_params['path']))

			if 'branch' in repo_params:
				repo.git.checkout('head', b=repo_params['branch'])

		self._create_base_files()

	def _create_base_files(self):
		"""Base files can be defined in the assembly file (see readme). Create
		them now."""
		if 'base_files' not in self.assembly.description:
			return
		for filename, file_desc in \
				self.assembly.description['base_files'].iteritems():
			open(os.path.join(self._working_copy_root,
							filename), 'w').write(file_desc['content'])

	def _create_katipo_root_folder(self, folder):
		"""Create a .katipo root folder."""
		# The reason for not placing .katipo_root in self immediately
		# is that if anything fails during clone we rm katipo_root
		# (since its probably in a messed up state).
		# We only want to do that if we created the folder.
		if not os.path.exists(folder):
			# Create parent folder if it doesn't already exist.
			os.mkdir(folder)
		katipo_root = os.path.join(folder, '.katipo')
		os.mkdir(os.path.join(katipo_root))
		self._katipo_root = katipo_root
		self._working_copy_root = os.path.abspath(folder)

	def run_cmd_per_repo(self, cmd, test_only=False):
		"""Run shell command (given as a list) for all repos (or only test repos)."""
		return_code = 0
		# Restore the parent environment for running external scripts
		env_vars = ['PATH', 'PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV']
		env_cmds = []
		for var in env_vars:
			try:
				parent_var = os.environ['KATIPO_PARENT_%s' % var]
				if parent_var == '':
					env_cmds += ['unset', var, '&&']
				else:
					env_cmds += ['export', '%s=%s' % (var, parent_var), '&&']
			except KeyError:
				# This occurs during test because parent var doesn't get set.
				logging.info('Not parent var %s' % var)
		cmd = env_cmds + cmd
		logging.info('Running cmd per repo %s' % str(cmd))
		for repo in self.assembly.repos:
			if not test_only or repo['test'] is True:
				p = subprocess.Popen(' '.join(cmd), cwd=os.path.abspath(
									os.path.join(self._working_copy_root,
												repo['path'])),
									shell=True, executable='/bin/bash')
				return_code += p.wait()
		return return_code

	def checkout(self, branch_name, tracking=False):
		"""Checkout branch in every repo."""
		# First see if this branch refers to an origin
		if len(branch_name.split('/')) > 1:
			origin = branch_name.split('/')[0]
		else:
			origin = None
		for repo in self.assembly.repos:
			logging.info('checkout %s in repo %s' % (branch_name, repo['path']))
			gitrepo = git.Repo(os.path.join(self._working_copy_root, repo['path']))
			try:
				if origin is not None:
					gitrepo.git.fetch(origin)
				if tracking:
					gitrepo.git.checkout('-t', branch_name)
				else:
					gitrepo.git.checkout(branch_name)
			except git.GitCommandError, e:
				logging.info('git checkout failed with %s' % e.message)
				print 'Branch doesn\'t exist on repo %s' % repo['path']

	def setup_virtualenv(self, python_exe=None):
		"""Create a python virtual in katipo_root/.env by concatenating all repos
		requirements.txt file. Also edit the active file to add the repos
		to the PYTHONPATH.

		python_exe passed to virtualenv is not None.
		prompt is also passed to virutalenv if not None"""

		requirements = []
		for repo in self.assembly.repos:
			try:
				this_repo_reqs = open(os.path.join(self._working_copy_root,
												repo['path'], 'requirements.txt')).read()
				requirements.append('# Reqs for %s\n' % repo['path']
								+ this_repo_reqs + '\n')
			except IOError:  # Ignore files that don't exist
				pass

		# Create a virtual env
		try:
			prompt = self.assembly.description['virtualenv']['prompt']
		except KeyError:
			prompt = None
		virtual_env_path = os.path.abspath(os.path.join(
													self._working_copy_root, 'venv'))
		if not os.path.exists(virtual_env_path):
			self._create_virtual_env(virtual_env_path, python_exe, prompt)

		# Add requirements.
		for req in requirements:
			self._add_virtualenv_requirements(virtual_env_path, req)

		for repo in self.assembly.repos:
			self._add_virtualenv_pythonpath(virtual_env_path,
							os.path.join(self._working_copy_root, repo['path']))

	def _add_virtualenv_pythonpath(self, virtual_env_path, python_path):
		"""Add PYTHONPATH from each repo to the virtual environment."""
		af = open(os.path.join(virtual_env_path, 'bin', 'activate'), 'a')
		af.write('\n# Katipo adding to PYTHONPATH\n')
		af.write('export PYTHONPATH="%s":$PYTHONPATH\n' % python_path)

	def _add_virtualenv_requirements(self, virtual_env_path, requirements):
		"""Add requirements to an existing virtual env in path."""
		reqfile = tempfile.NamedTemporaryFile()
		reqfile.write(requirements)
		reqfile.flush()

		# Workaround on OS X - install readline.
		if sys.platform == 'darwin':
			os.system('. %s/bin/activate && easy_install '
					' -i http://pypi.braincorporation.net/simple'
					' readline ' %
					virtual_env_path)

		os.system('. %s/bin/activate && pip install -r %s '
					' -i http://pypi.braincorporation.net/simple' %
					(virtual_env_path, reqfile.name))

	def _create_virtual_env(self, virtual_env_path, python_exe, prompt):
		"""Create an empty virtual env"""
		options = '--prompt %s' % prompt if prompt is not None else ''
		options += ' -p %s' % python_exe if python_exe is not None else ''
		options += ' --distribute'  # Use disttools
		os.system('virtualenv %s "%s"' % (options, virtual_env_path))
