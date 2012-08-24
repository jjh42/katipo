# ===========================================================================
#
#  COPYRIGHT 2012 Brain Corporation.
#  All rights reserved. Brain Corporation proprietary and confidential.
#
#  The party receiving this software directly from Brain Corporation
#  (the "Recipient" ) may use this software and make copies thereof as
#  reasonably necessary solely for the purposes set forth in the agreement
#  between the Recipient and Brain Corporation ( the "Agreement" ). The
#  software may be used in source code form
#  solely by the Recipient's employees. The Recipient shall have no right to
#  sublicense, assign, transfer or otherwise provide the source code to any
#  third party. Subject to the terms and conditions set forth in the Agreement,
#  this software, in binary form only, may be distributed by the Recipient to
#  its customers. Brain Corporation retains all ownership rights in and to
#  the software.
#
#  This notice shall supercede any other notices contained within the software.
# =============================================================================
import unittest

import cmdline
from test_reposetup import TestWithRepoSetup
import os


class TestClone(TestWithRepoSetup):
	test_repo_description = {
				'katipo_schema': 1,
				'repos': [
				{'path': "test", 'test': True,
					'files': {'test': {'content': '#!/bin/sh\necho Testing\n',
										'exec': True}}},
				{'path': 'notest', 'test': False,
					'files': {'notest': {'content': 'Hello\n'}}}
				]}

	def clone(self):
		"""Make working copy (used in other tests)."""
		cmdline.run_args(['clone', os.path.join(self.tempfolder, 'gitrepos',
				'assemblies'), 'testassembly.katipo'], working_dir=
				os.path.join(self.tempfolder, 'workingcopy'))

	def test_clone(self):
		self.clone()
		# Check that the two repos in the assembly were created properly
		os.stat(os.path.join(self.tempfolder, 'workingcopy', 'test', 'test'))
		os.stat(os.path.join(self.tempfolder, 'workingcopy', 'notest', 'notest'))

	def test_perrepo(self):
		self.clone()
		cmdline.run_args(['perrepo', 'ls', '-l'], working_dir=
				os.path.join(self.tempfolder, 'workingcopy'))