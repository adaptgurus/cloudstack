// Licensed to the Apache Software Foundation (ASF) under one
// or more contributor license agreements. See the NOTICE file
// distributed with this work for additional information
// regarding copyright ownership. The ASF licenses this file
// to you under the Apache License, Version 2.0 (the
// "License"); you may not use this file except in compliance
// with the License. You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an
// "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
// KIND, either express or implied. See the License for the
// specific language governing permissions and limitations
// under the License.

const types = {
  403: {
    code: '403',
    title: 'Access restricted',
    desc: 'LayerSentry could not authorize this page or action for the current session. Return to an authorized area or ask your administrator to review the required CloudStack permissions.'
  },
  404: {
    code: '404',
    title: 'Page not found',
    desc: 'LayerSentry could not find this page or resource. It may have been removed, the address may be incorrect, or the current scope may no longer expose it.'
  },
  500: {
    code: '500',
    title: 'Request could not be completed',
    desc: 'LayerSentry encountered an unexpected application error. Return to the dashboard and retry the operation after checking any available activity or job details.'
  }
}

export default types
