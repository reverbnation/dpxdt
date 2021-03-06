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

"""Entry point for the App Engine environment."""

# Local Libraries
import gae_mini_profiler.profiler
import gae_mini_profiler.templatetags

# Local modules
from dpxdt.server import app


@app.route('/_ah/warmup')
def appengine_warmup():
    return 'OK'


@app.context_processor
def gae_mini_profiler_context():
    return dict(
        profiler_includes=gae_mini_profiler.templatetags.profiler_includes)


application = gae_mini_profiler.profiler.ProfilerWSGIMiddleware(app)
