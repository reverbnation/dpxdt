#!/usr/bin/env python
# Copyright 2013 Brett Slatkin
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Background worker that generates 200x200 thumbnails, possibly from a queue."""

import Queue
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib2

# Local Libraries
import gflags
FLAGS = gflags.FLAGS

# Local modules
from dpxdt import constants
from dpxdt.client import process_worker
from dpxdt.client import queue_worker
from dpxdt.client import release_worker
from dpxdt.client import workers


gflags.DEFINE_integer(
    'thumb_task_max_attempts', 3,
    'Maximum number of attempts for processing a thumbnail task.')

gflags.DEFINE_integer(
    'thumb_wait_seconds', 3,
    'Wait this many seconds between repeated invocations of thumbnail '
    'subprocesses. Can be used to spread out load on the server.')

gflags.DEFINE_integer(
    'thumb_threads', 1, 'Number of thumbnail generation threads to run')

gflags.DEFINE_integer(
    'thumb_timeout', 60,
    'Seconds until we should give up on a thumbnail sub-process and try again.')

gflags.DEFINE_integer(
    'thumb_size', 200,
    'Size of the square thumbnails to generate.')

class ThumbFailedError(queue_worker.GiveUpAfterAttemptsError):
    """Running a thumbnail worker failed for some reason."""


class ResizeWorkflow(process_worker.ProcessWorkflow):
    """Workflow for resizing images into thumbnails."""

    def __init__(self, log_path, image_path, resized_path):
        """Initializer.

        Args:
            log_path: Where to write the verbose logging output.
            image_path: Path to referenced screenshot
            resized_path: Where the resized thumbnail should be written.
        """
        process_worker.ProcessWorkflow.__init__(
            self, log_path, timeout_seconds=FLAGS.thumb_timeout)
        self.image_path = run_path
        self.resized_ref_path = resized_ref_path

    def get_args(self):
        return [
            'convert',
            self.image_path,
            '-thumbnail 200',
            '-crop 200x200+0+0\!'
            '-background white',
            '-flatten',
            self.resized_path
        ]

class DoThumbQueueWorkflow(workers.WorkflowItem):
    """Runs the thumbnail creation from queue parameters.

    Args:
        build_id: ID of the build.
        release_name: Name of the release.
        release_number: Number of the release candidate.
        run_name: Run to run perceptual diff for.
        run_sha1sum: Content hash of the new image.
        diff_sha1sum: Content hash of the diffed image.
        heartbeat: Function to call with progress status.

    Raises:
        ThumbFailedError if the perceptual diff process failed.
    """

    def run(self, build_id=None, release_name=None, release_number=None,
            run_name=None, run_sha1sum=None, diff_sha1sum=None, heartbeat=None):
        output_path = tempfile.mkdtemp()
        try:
            run_path = os.path.join(output_path, 'run')
            diff_path = os.path.join(output_path, 'diff')
            resized_path = os.path.join(output_path, 'resized')
            run_thumb_path = os.path.join(output_path, 'run_thumb.png')
            diff_thumb_path = os.path.join(output_path, 'diff_thumb.png')
            log_path = os.path.join(output_path, 'log.txt')

            yield heartbeat('Fetching reference and run images')
            yield [
                release_worker.DownloadArtifactWorkflow(
                    build_id, run_sha1sum, result_path=run_path),
                release_worker.DownloadArtifactWorkflow(
                    build_id, diff_sha1sum, result_path=diff_path)
            ]

            max_attempts = FLAGS.thumb_task_max_attempts

            yield heartbeat('Resizing to thumbnail size')
            returncode = yield [
                ResizeWorkflow(
                    log_path, run_path, run_thumb_path),
                ResizeWorkflow(
                    log_path, diff_path, diff_thumb_path)
            ]
            if returncode != 0:
                raise ThumbFailedError(
                    max_attempts,
                    'Could not resize thumbnails')
        finally:
            shutil.rmtree(output_path, True)


def register(coordinator):
    """Registers this module as a worker with the given coordinator."""
    assert FLAGS.thumb_threads > 0
    assert FLAGS.queue_server_prefix

    item = queue_worker.RemoteQueueWorkflow(
        constants.THUMB_QUEUE_NAME,
        DoThumbQueueWorkflow,
        max_tasks=FLAGS.thumb_threads,
        wait_seconds=FLAGS.thumb_wait_seconds)
    item.root = True
    coordinator.input_queue.put(item)
