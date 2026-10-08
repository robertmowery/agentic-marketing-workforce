# Copyright 2026 Robert H. Mowery III
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

"""The team that gets deployed: Part 2's hybrid with a home for house rules.

A Director that saves standing rules to user-scoped state, and a pipeline that
reads them. It is the build from ``workforce.context.handoff`` unchanged, so
anything this service does differently from a laptop run is down to where it
runs, not to what it is.
"""

from workforce.context import handoff

root_agent = handoff.build_hybrid_with_rules()
